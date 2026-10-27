"""One application per causal event per scenario. Citations are not multipliers."""
import re


def canonical(value):
    if not isinstance(value,str) or not value.strip():raise ValueError('effect needs canonical event_id')
    value=re.sub(r'[^a-z0-9]+',':',value.strip().lower()).strip(':')
    # These are overlapping descriptions of one read-mix adjustment, not
    # independent uplift channels. Keep team/season prefixes intact.
    for suffix in ('first:read:suppression','forced:checkdown','checkdown:funnel'):
        if value.endswith(':'+suffix):value=value[:-len(suffix)]+'read:tendency'
    return value


def fact_events(fact):
    if not isinstance(fact,dict):raise ValueError('effect evidence missing')
    event=fact.get('causal_event')
    if event is not None:
        if not isinstance(event,dict) or any(not event.get(k) for k in ('kind','entity_id','effective_date')):
            raise ValueError('causal_event requires kind, entity_id and effective_date')
        if event.get('parent_event_id'):return [canonical(event['parent_event_id'])]
        return [canonical(':'.join(str(event[k]) for k in ('kind','entity_id','effective_date')))]
    ids=fact.get('event_ids')
    if ids is None:ids=[fact.get('event_id')]
    if not isinstance(ids,list) or not ids:raise ValueError('numeric context change needs an event identity')
    result=[canonical(x) for x in ids]
    if len(result)!=len(set(result)):raise ValueError('duplicate event in combined effect evidence')
    return result


def audit_scenario(row,covered,automatic=None):
    """An event may span multiple inputs in one joint record, never two effects.

    Explicitly embedded events can be cited again as evidence, but not applied as
    another adjustment. Events may recur across mutually exclusive scenarios.
    """
    embedded=row.get('embedded_event_ids',[])
    if not isinstance(embedded,list):raise ValueError('embedded_event_ids must be a list')
    embedded={canonical(x) for x in embedded}
    seen=set();ledger=[]
    effects=row.get('applied_effects',[])
    if not isinstance(effects,list):raise ValueError('applied_effects must be a list')
    for effect in list(automatic or [])+effects:
        if not isinstance(effect,dict):raise ValueError('invalid effect record')
        if 'source_driver' in effect:
            fact=covered.get(effect['source_driver'])
            events=fact_events(fact)
            if canonical(effect.get('event_id')) not in events:raise ValueError('effect event does not match sourced driver')
        else:events=[canonical(effect.get('event_id'))]
        inputs=effect.get('inputs')
        if not isinstance(inputs,list) or not inputs or len(inputs)!=len(set(inputs)):
            raise ValueError('effect must identify its jointly affected inputs once')
        for event in events:
            if event in embedded:raise ValueError('effect already embedded in baseline: '+event)
            if event in seen:raise ValueError('duplicate causal effect: '+event)
            seen.add(event)
            ledger.append({'event_id':event,'inputs':inputs,'applied_by':effect.get('applied_by','scenario_assumption')})
    return ledger
