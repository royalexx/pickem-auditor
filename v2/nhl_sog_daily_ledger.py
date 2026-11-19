"""Research-only transactional freeze/outcome ledger. No pregame network or fitting.

Admission is deliberately inside prospective_shadow_attempt after existing signed
source, quote and roster verification. Fixture clock injection is for tests only.
Full infinite laws are frozen as parameters; finite PMF arrays have explicit
unallocated tail mass and are NEVER renormalized or used to truncate log scores.
"""
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import hashlib
import json
import math
import re
import sqlite3
from .nhl_sog_exposure_shadow import _mass

KINDS = {'M0': 'plugin_poisson', 'M1': 'mixture_exposure_plugin_poisson',
         'M2': 'fixed_exposure_gamma_poisson', 'M3': 'full_gamma_poisson_exposure',
         'M4': 'nb2_fixed_shape4'}


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(x):
    return hashlib.sha256(canonical(x)).hexdigest()


def utc(x):
    d = datetime.fromisoformat(x.replace('Z', '+00:00'))
    if d.tzinfo is None:
        raise ValueError('NAIVE_TIME')
    return d.astimezone(timezone.utc)


def mass(model, k, kind):
    if kind != 'nb2_fixed_shape4':
        return _mass(model, k, kind)
    mu = model['plugin_rate'] * model['plugin_exposure']
    if mu == 0:
        return float(k == 0)
    a = 4.0
    return math.exp(math.lgamma(a+k)-math.lgamma(a)-math.lgamma(k+1)
                    + a*math.log(a/(a+mu))+k*math.log(mu/(a+mu)))


def law(model, kind):
    for key in ('rate_a', 'rate_b', 'plugin_rate', 'plugin_exposure'):
        v = model[key]
        if isinstance(v, bool) or not math.isfinite(v) or v < 0:
            raise ValueError('INVALID_MODEL_PARAMETER')
    if model['rate_a'] <= 0 or model['rate_b'] <= 0 or model['plugin_exposure'] <= 0:
        raise ValueError('INVALID_MODEL_PARAMETER')
    pi = model['exposure_pmf']
    if not pi or any(not math.isfinite(w+p) or w <= 0 or p < 0 for w,p in pi):
        raise ValueError('INVALID_EXPOSURE_PMF')
    if abs(math.fsum(p for w,p in pi)-1) > 1e-12:
        raise ValueError('INVALID_EXPOSURE_PMF')
    ps=[]
    for k in range(4096):
        p=mass(model,k,kind)
        if not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError('INVALID_COUNT_PMF')
        ps.append(p)
        total=math.fsum(ps)
        if total > 1+1e-12:
            raise ValueError('INVALID_COUNT_PMF')
        if 1-total <= 1e-13:
            return {'kind':kind, 'parameters':model, 'pmf_from_zero':ps,
                    'tail_mass':max(0.,1-total), 'tail_after':k,
                    'tail_evaluator':'v2.nhl_sog_daily_ledger.mass/v1',
                    'normalization':'analytic_infinite_law_no_truncation_renormalization'}
    raise ValueError('COUNT_TAIL_NOT_CERTIFIED')


class Ledger:
    def __init__(self,path):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path, timeout=30)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS forecasts(id TEXT PRIMARY KEY, contract TEXT,
            model TEXT, slate TEXT, body BLOB, UNIQUE(contract,model));
        CREATE TABLE IF NOT EXISTS outcomes(id TEXT PRIMARY KEY, forecast TEXT,
            previous TEXT, body BLOB);
        CREATE TABLE IF NOT EXISTS heads(forecast TEXT PRIMARY KEY, outcome TEXT);
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, body BLOB);
        CREATE TABLE IF NOT EXISTS freeze_receipts(contract TEXT PRIMARY KEY, body BLOB);
        ''')

    def freeze(self,contract,model,*,run_id,code_sha,now=None):
        injected=now is not None
        now=now or datetime.now(timezone.utc)
        if any(k in model for k in ("actual_sog","actual_toi","realized_ice_time","final_boxscore")):
            raise ValueError("OUTCOME_FEATURE_FORBIDDEN")
        start=utc(contract['event_start_at'])
        cutoff=start-timedelta(minutes=3)
        if now>=cutoff:raise ValueError("PREGAME_CUTOFF_MISSED")
        if not utc(contract['quote_at']) <= utc(model['input_freeze_at']) <= now < start:
            raise ValueError('NOT_PREGAME')
        if utc(model['fit_data_cutoff_at']) > utc(model['input_freeze_at']):
            raise ValueError('FUTURE_FEATURE')
        if any(utc(s['received_at']) > utc(model['input_freeze_at']) for s in model['source_manifest']):
            raise ValueError('FUTURE_FEATURE')
        if (str(model['player_id']) != str(contract['player_id']) or
            model['target_event_id'] != contract['event_id'] or
            model['current_team_id'] != contract['team_id'] or
            utc(model['event_start_at']) != start):
            raise ValueError('MODEL_CONTRACT_IDENTITY_DRIFT')
        if len(code_sha)!=40 or any(c not in '0123456789abcdef' for c in code_sha):
            raise ValueError('CODE_SHA_REQUIRED')
        # Ignore changing quote IDs/payload SHA for repeated observations of same market.
        key=digest([contract[k] for k in ('official_game_id','player_id','team_id',
                    'opponent_id','stat_key','period','book','line','settlement_policy')])
        if contract['stat_key']!='shots on goal' or contract['period']!='full':
            raise ValueError('WRONG_MARKET')
        if contract['settlement_policy']!='strict_gt_lt_equal_push':
            raise ValueError('UNSUPPORTED_SETTLEMENT')
        generated=now.isoformat()
        rows=[]
        for name,kind in KINDS.items():
            distribution=law(model,kind)
            line=contract['line'];ps=distribution['pmf_from_zero']
            under=math.fsum(p for k,p in enumerate(ps) if k<line)
            push=mass(model,int(line),kind) if float(line).is_integer() else 0.
            body={'schema':'nhl_sog_daily_frozen/1','model':name,'version':kind+'/1',
                  'contract_key':key,'contract':contract,'distribution':distribution,
                  'over':1-under-push,'under':under,'push':push,
                  'run_id':run_id,'code_sha':code_sha,
                  'daily_implementation_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'generated_at':generated,
                  'freeze_started_at':generated,'frozen_at':None,'freeze_clock_semantics':'separate_verified_commit_receipt','freeze_cutoff_at':cutoff.isoformat(),'eligibility':'SYNTHETIC_FIXTURE_NOT_SOURCE_CERTIFIED' if injected else 'source_verified_played_game_conditional',
                  'evidence_class':'SYNTHETIC' if injected else 'PROSPECTIVE_CANDIDATE_REQUIRING_COMMIT_RECEIPT',
                  'research_only':True,'promotion_allowed':False}
            rows.append((digest(body),key,name,start.astimezone(ZoneInfo('America/Toronto')).date().isoformat(),canonical(body)))
        # Recheck actual wall time after inference; never use a generation-start
        # clock as proof that persistence completed before the cutoff.
        finished=now if injected else datetime.now(timezone.utc)
        if finished >= cutoff:
            raise ValueError('FREEZE_COMPLETED_AFTER_START')
        finalized=[]
        for _,key,name,slate,raw in rows:
            body=json.loads(raw);body['freeze_started_at']=finished.isoformat()
            finalized.append((digest(body),key,name,slate,canonical(body)))
        rows=finalized
        archive=Path(self.db.execute('PRAGMA database_list').fetchone()[2]).parent/'forecasts'
        # Five candidate rows commit together or roll back together, including crash.
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if not injected and datetime.now(timezone.utc)>=cutoff:
                raise ValueError("FREEZE_TRANSACTION_AFTER_START")
            added=0
            for row in rows:
                atomic_blob(archive/(row[0]+'.json'),row[4])
                added+=self.db.execute('INSERT OR IGNORE INTO forecasts VALUES(?,?,?,?,?)',row).rowcount
        existing=self.db.execute('SELECT body FROM freeze_receipts WHERE contract=?',(key,)).fetchone()
        if existing:commit=json.loads(existing[0])
        else:
            # This clock is sampled AFTER payload verification and the first
            # durable SQL commit. No recomputation is substituted for stored rows.
            verified=now if injected else datetime.now(timezone.utc)
            if verified>=cutoff:raise ValueError('FREEZE_COMMIT_AFTER_CUTOFF')
            stored=self.db.execute('SELECT id,body FROM forecasts WHERE contract=? ORDER BY model',(key,)).fetchall()
            if len(stored)!=len(KINDS):raise ValueError('INCOMPLETE_STORED_FAMILY')
            for fid,raw in stored:
                if digest(json.loads(raw))!=fid:raise ValueError('FROZEN_FORECAST_HASH_DRIFT')
                if (archive/(fid+'.json')).read_bytes()!=raw:raise ValueError('STORED_FORECAST_BYTES_DRIFT')
            commit={'schema':'nhl_sog_freeze_commit/1','contract':key,
                    'forecast_ids':[r[0] for r in stored],'frozen_at':verified.isoformat(),
                    'freeze_cutoff_at':cutoff.isoformat(),'synthetic_fixture':injected}
            with self.db:
                self.db.execute('BEGIN IMMEDIATE')
                atomic_blob(archive.parent/'freeze_receipts'/(digest(commit)+'.json'),canonical(commit))
                self.db.execute('INSERT OR IGNORE INTO freeze_receipts VALUES(?,?)',(key,canonical(commit)))
        return {'newly_frozen':added,'previously_frozen':len(rows)-added,'contract':key,
                'freeze_commit_sha256':digest(commit),'frozen_at':commit['frozen_at']}

    def settle(self,fetch,*,run_id):
        counts={'newly_settled':0,'previously_settled':0,'corrections':0,'pending':0,'unresolved':0}
        cache={}
        records=[]
        for fid,body in self.db.execute('SELECT id,body FROM forecasts ORDER BY slate,id').fetchall():
            f=json.loads(body);c=f['contract'];gid=str(c['official_game_id'])
            try:
                if digest(f)!=fid:raise ValueError("FROZEN_FORECAST_HASH_DRIFT")
                freeze=self.db.execute('SELECT body FROM freeze_receipts WHERE contract=?',(f['contract_key'],)).fetchone()
                if not freeze:raise ValueError('UNCONFIRMED_FREEZE_NOT_PROSPECTIVE')
                freeze=json.loads(freeze[0])
                if fid not in freeze['forecast_ids'] or utc(freeze['frozen_at'])>=utc(f['freeze_cutoff_at']):
                    raise ValueError('FREEZE_RECEIPT_IDENTITY_OR_CUTOFF_INVALID')
                if gid not in cache:
                    cache[gid]=fetch(gid)
                doc,receipt=cache[gid]
                if str(doc.get('id'))!=gid:
                    raise ValueError('OFFICIAL_GAME_ID_MISMATCH')
                if receipt['sha256']!=hashlib.sha256(receipt['raw']).hexdigest() or json.loads(receipt['raw'])!=doc:
                    raise ValueError('OFFICIAL_RECEIPT_DRIFT')
                if receipt['url']!='https://api-web.nhle.com/v1/gamecenter/'+gid+'/boxscore':
                    raise ValueError('OFFICIAL_ENDPOINT_INVALID')
                if utc(receipt['received_at']) < utc(c['event_start_at']):
                    raise ValueError('OUTCOME_BEFORE_GAME')
                source=Path(self.db.execute('PRAGMA database_list').fetchone()[2]).parent/'official'/receipt['sha256']
                with self.db:
                    self.db.execute('BEGIN IMMEDIATE')
                    atomic_blob(source,receipt['raw'])
                if doc.get('gameScheduleState') in ('PPD','CNCL','CANCELLED'):
                    raise ValueError('POSTPONED_OR_CANCELLED_ORIGINAL_CONTRACT_REVIEW')
                if doc.get('startTimeUTC') and utc(doc['startTimeUTC'])!=utc(c['event_start_at']):
                    raise ValueError('RESCHEDULED_GAME_ORIGINAL_CONTRACT_REVIEW')
                if doc.get('gameState') not in ('OFF','FINAL'):
                    counts['pending']+=1;records.append({'forecast':fid,'status':'PENDING_OFFICIAL_FINAL','source_sha256':receipt['sha256']});continue
                if {doc[z]['abbrev'] for z in ('homeTeam','awayTeam')}!={c['team_id'],c['opponent_id']}:
                    raise ValueError('OFFICIAL_TEAMS_MISMATCH')
                matches=[]
                for team in ('homeTeam','awayTeam'):
                    for group in ('forwards','defense','defensemen'):
                        for p in doc.get('playerByGameStats',{}).get(team,{}).get(group,[]):
                            if str(p.get('playerId'))==str(c['player_id']):
                                matches.append((doc[team]['abbrev'],p))
                if len(matches)!=1 or matches[0][0]!=c['team_id']:
                    raise ValueError('DNP_MISSING_OR_TRADE_IDENTITY_UNRESOLVED')
                player=matches[0][1];y=player.get('sog')
                toi=player.get('toi')
                valid_toi=isinstance(toi,str) and re.fullmatch(r'[0-9]+:[0-5][0-9]',toi)
                played=bool(valid_toi) and sum(int(x) for x in toi.split(':'))>0
                if type(y)!=int or y<0 or not played:
                    raise ValueError('PLAYED_STATUS_OR_SOG_UNVERIFIED')
                out={'forecast_id':fid,'official_sog':y,'source_sha256':receipt['sha256'],
                     'source_url':receipt['url'],'scores':score(f,y)}
                old=self.db.execute('SELECT outcome FROM heads WHERE forecast=?',(fid,)).fetchone()
                if old:
                    prior=json.loads(self.db.execute('SELECT body FROM outcomes WHERE id=?',old).fetchone()[0])
                    if prior['official_sog']==y and prior['source_sha256']==receipt['sha256']:
                        counts['previously_settled']+=1;records.append({'forecast':fid,'status':'PREVIOUSLY_SETTLED'});continue
                out.update(previous=old[0] if old else None,received_at=receipt['received_at'])
                oid=digest(out)
                # Raw official receipt is retained separately from immutable forecasts.
                source=Path(self.db.execute('PRAGMA database_list').fetchone()[2]).parent/'official'/receipt['sha256']
                atomic_blob(source,receipt['raw'])
                with self.db:
                    self.db.execute('INSERT OR IGNORE INTO outcomes VALUES(?,?,?,?)',(oid,fid,out['previous'],canonical(out)))
                    self.db.execute('INSERT OR REPLACE INTO heads VALUES(?,?)',(fid,oid))
                counts['corrections' if old else 'newly_settled']+=1
                records.append({'forecast':fid,'status':'CORRECTED' if old else 'NEWLY_SETTLED','outcome':oid})
            except (OSError,ValueError,KeyError,TypeError) as exc:
                counts['unresolved']+=1
                records.append({'forecast':fid,'status':'UNRESOLVED','reason':str(exc)})
                counts.setdefault('reasons',{}).setdefault(str(exc),0)
                counts['reasons'][str(exc)]+=1
        counts['unique_forecast_dates']=self.db.execute('SELECT count(DISTINCT f.slate) FROM forecasts f JOIN freeze_receipts r ON f.contract=r.contract').fetchone()[0]
        counts['unique_settled_contracts']=self.db.execute('SELECT count(DISTINCT f.contract) FROM forecasts f JOIN heads h ON f.id=h.forecast').fetchone()[0]
        counts['run_id']=run_id
        counts['records']=records
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO runs VALUES(?,?)',(digest(counts),canonical(counts)))
        return counts


def atomic_blob(path,raw):
    """Immutable verified object, including object stores without hard links.

    Ledger callers hold the SQL writer lock. A completion marker is written
    only after exact-byte verification; an uncommitted partial content-addressed
    object can be quarantined and retried. Completed objects are never replaced.
    """
    import os,tempfile,errno
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    expected=hashlib.sha256(raw).hexdigest();marker=path.with_name(path.name+'.complete')
    if path.exists():
        current=path.read_bytes()
        if current!=raw:
            if marker.exists() or path.stem!=expected and path.name!=expected:
                raise ValueError('IMMUTABLE_BLOB_CHANGED')
            damaged=path.with_name(path.name+'.incomplete.'+hashlib.sha256(current).hexdigest())
            if not damaged.exists():
                with damaged.open('xb') as f:f.write(current)
            path.unlink() # Only an uncommitted partial object, never a completed freeze.
    if not path.exists():
        fd,tmp=tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
            try:os.link(tmp,path)
            except FileExistsError:pass
            except OSError as exc:
                if exc.errno not in (errno.ENOTSUP,errno.EOPNOTSUPP):raise
                try:
                    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
                except FileExistsError:pass
        finally:os.unlink(tmp)
    if path.read_bytes()!=raw:raise ValueError('IMMUTABLE_BLOB_CHANGED')
    stamp=expected.encode()
    if marker.exists() and marker.read_bytes()!=stamp:
        broken=marker.with_name(marker.name+'.incomplete.'+hashlib.sha256(marker.read_bytes()).hexdigest())
        if not broken.exists():broken.write_bytes(marker.read_bytes())
        marker.unlink()
    try:
        with marker.open('xb') as f:f.write(stamp);f.flush();os.fsync(f.fileno())
    except FileExistsError:pass
    if marker.read_bytes()!=stamp:raise ValueError('OBJECT_COMPLETION_MARKER_INVALID')


def score(f,y):
    d=f['distribution'];model=d['parameters'];kind=d['kind']
    ps=list(d['pmf_from_zero'])
    for k in range(len(ps),y+1):ps.append(mass(model,k,kind))
    exposure=model['plugin_exposure'] if kind in ('plugin_poisson','fixed_exposure_gamma_poisson','nb2_fixed_shape4') else math.fsum(w*p for w,p in model['exposure_pmf'])
    rate=model['rate_a']/model['rate_b'] if kind in ('fixed_exposure_gamma_poisson','full_gamma_poisson_exposure') else model['plugin_rate']
    mean=rate*exposure
    cdf=0.;crps=0.;quantiles={};before=math.fsum(ps[:y])
    for k,p in enumerate(ps):
        cdf+=p;crps+=(cdf-float(y<=k))**2
        for q in (.05,.25,.5,.75,.95):
            if cdf>=q and str(q) not in quantiles:quantiles[str(q)]=k
    u=int(hashlib.sha256(f['contract_key'].encode()).hexdigest()[:13],16)/16**13
    line=f['contract']['line'];state='over' if y>line else 'under' if y<line else 'push'
    prob={k:f[k] for k in ('over','under','push')}
    return {'count_CRPS':crps,'count_NLPD':-math.log(max(mass(model,y,kind),1e-300)),
            'mean':mean,'absolute_error':abs(mean-y),'squared_error':(mean-y)**2,
            'signed_bias':mean-y,'randomized_PIT':before+u*mass(model,y,kind),
            'quantiles':quantiles,'quantile_covered':{q:y<=k for q,k in quantiles.items()},
            'zero_probability':ps[0],'zero_observed':y==0,
            'tail_ge6_probability':1-math.fsum(ps[:6]),'tail_ge6_observed':y>=6,
            'original_market_outcome':state,'market_probability':prob[state],
            'market_log_score':-math.log(max(prob[state],1e-300)),
            'market_Brier':math.fsum((prob[k]-float(k==state))**2 for k in prob)}


def cumulative_report(ledger):
    """Persist descriptive matched scores; no winner, significance or promotion."""
    from collections import defaultdict
    cohorts=defaultdict(dict)
    for fid,contract,model,slate,raw,oraw in ledger.db.execute('''
        SELECT f.id,f.contract,f.model,f.slate,f.body,o.body FROM forecasts f
        JOIN heads h ON f.id=h.forecast JOIN outcomes o ON o.id=h.outcome
        ORDER BY f.slate,f.contract,f.model'''):
        f=json.loads(raw);o=json.loads(oraw)
        if digest(f)!=fid:raise ValueError('FROZEN_FORECAST_HASH_DRIFT')
        cohorts[(slate,contract)][model]=o['scores']
    matched={k:v for k,v in cohorts.items() if set(v)==set(KINDS)}
    metrics={}
    for model in KINDS:
        rows=[v[model] for v in matched.values()]
        keys=('count_CRPS','count_NLPD','absolute_error','squared_error','signed_bias',
              'market_Brier','market_log_score','zero_probability','tail_ge6_probability')
        metrics[model]={k:math.fsum(r[k] for r in rows)/len(rows) if rows else None for k in keys}
        metrics[model]['RMSE']=math.sqrt(metrics[model]['squared_error']) if rows else None
    per_date={d:{'matched_player_games':sum(k[0]==d for k in matched)}
              for d in sorted({k[0] for k in matched})}
    return {'schema':'nhl_sog_cumulative_matched/1','matched_contracts':len(matched),
            'distinct_dates':len(per_date),'chronological_coverage':per_date,
            'unmatched_contracts':len(cohorts)-len(matched),'metrics':metrics,
            'uncertainty_status':'BLOCKED_NO_APPROVED_DAILY_FAMILY_INFERENCE_PROTOCOL',
            'comparisons_are_descriptive_only':True,'promotion_allowed':False}
