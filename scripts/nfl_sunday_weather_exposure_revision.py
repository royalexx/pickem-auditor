"""Append roof evidence revision; preserve initial capture and all source clocks."""
from copy import deepcopy
import json
import re
from scripts import nfl_sunday_weather as w

def main():
    parent=w.OUT/'WEATHER_FEATURE_PIN.json'
    target=w.OUT/'revision_2'/'WEATHER_FEATURE_PIN.json'
    if target.exists():
        pin=json.loads(target.read_bytes()); w.validate(pin); return
    pin=deepcopy(json.loads(parent.read_bytes()))
    urls={
        '401873059':['https://www.lucasoilstadium.com/', 'https://www.lucasoilstadium.com/stadium-info/'],
        '401873055':['https://www.caesarssuperdome.com/', 'https://www.caesarssuperdome.com/about-us'],
        '401873062':['https://www.allegiantstadium.com/', 'https://www.allegiantstadium.com/stadium-information'],
        '401873063':['https://attstadium.com/', 'https://attstadium.com/stadium-info/facts-figures/'],
    }
    for row in pin['events']:
        if row['game_id'] not in urls: continue
        if w.stamp(w.now()) >= w.stamp(row['kickoff_at']): raise ValueError('KICKOFF_PASSED')
        matches=[]
        for i,url in enumerate(urls[row['game_id']]):
            b,rec=w.fetch(row['game_id']+'_roof_revision_'+str(i),url)
            row['sources'].append(rec)
            text=re.sub(r'\s+',' ',re.sub('<[^>]+>',' ',b.decode('utf8',errors='replace'))) if b else ''
            patterns=(r'retractable[ -]+roof' if row['proposed_stadium_type']=='retractable'
                      else r'fixed[ -]+roof|domed|fully[ -]+enclosed|enclosed[ -]+stadium|climate[ -]+controlled')
            for m in re.finditer(patterns,text,re.I):
                matches.append({'source_sha256':rec['sha256'],'excerpt':text[max(0,m.start()-150):m.end()+200]})
        # Retractable doors do not prove a retractable roof.
        if matches:
            row['stadium_type']=row['proposed_stadium_type']
            row['uncertainty']=[x for x in row['uncertainty'] if x!='STADIUM_TYPE_NOT_VERIFIED']
        else:
            row['stadium_type']='unverified'
            if 'STADIUM_TYPE_NOT_VERIFIED' not in row['uncertainty']: row['uncertainty'].append('STADIUM_TYPE_NOT_VERIFIED')
        row['exposure']=w.exposure(row['stadium_type'],'unknown',None)
        row['roof_evidence_revision']=matches
        row['prior_weather_feature_freeze_at']=row['weather_feature_freeze_at']
        row['weather_feature_freeze_at']=w.now()
    pin['parent_weather_pin']={'path':str(parent),'sha256':w.sha(parent.read_bytes())}
    pin['revision']='2-original-stadium-evidence-append-only'
    pin['event_table']=w.save(target.parent/'events.jsonl',b''.join(w.canonical(r) for r in pin['events']))
    pin['summary']['exposure_unverified']=sum(r['exposure']=='EXPOSURE_UNVERIFIED' and r['status']!='EXCLUDED_ALREADY_STARTED' for r in pin['events'])
    pin['summary']['retractable_roof_status_unknown']=sum(r['exposure']=='RETRACTABLE_ROOF_STATUS_UNKNOWN' for r in pin['events'])
    w.validate(pin); d=w.save(target,w.canonical(pin)); print(json.dumps(d),pin['summary'])

if __name__=='__main__': main()
