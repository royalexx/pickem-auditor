"""Source-bound subset request handoff. This is not a model/forecast envelope."""
import hashlib
import json
from pathlib import Path
from .research_profile_v1 import build_requests

VERSION='nba-p1-subset-handoff/1.0.0'

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(raw):return hashlib.sha256(raw).hexdigest()

def export_requests(capture_dir,cohort):
    path=Path(capture_dir)
    requests=build_requests(path,cohort)
    sources={}
    for name in ['scoreboard']+['roster-'+tid for tid in cohort['teams']]+['official-'+abbr.lower()+'-roster' for abbr in cohort['teams'].values()]:
        folder=path/name
        sources[name]={f:digest((folder/f).read_bytes()) if (folder/f).is_file() else None for f in ('body.raw','receipt.json')}
    payload=dict(schema=VERSION,kind='SOURCE_LISTED_RESEARCH_REQUESTS',cohort=cohort,
        source_file_hashes=sources,requests=requests,model_attached=False,
        forecasted_rows=0,source_admission='RESEARCH_BYTES_CONSISTENCY_ONLY')
    return dict(payload,payload_sha256=digest(canonical(payload)))


def read_requests(raw,capture_dir,cohort):
    """Replay from raw sources, not caller approvals or resealed payload claims."""
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError('DUPLICATE_HANDOFF_KEY')
            result[k]=v
        return result
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('NONFINITE_HANDOFF')))
    expected=export_requests(capture_dir,cohort)
    if canonical(value)!=canonical(expected):raise ValueError('HANDOFF_SOURCE_OR_REQUEST_MISMATCH')
    return value


def conditional_requests(raw,capture_dir,cohort):
    value=read_requests(raw,capture_dir,cohort)
    ready=[r for r in value['requests']['rows'] if r['source_request_status']=='SOURCE_READY_CONDITIONAL_REQUEST']
    return dict(schema=VERSION,consumer='CONDITIONAL_RESEARCH_REQUEST_BOUNDARY',
        source_handoff_sha256=value['payload_sha256'],candidate_denominator=value['requests']['source_candidate_rows'],
        requests=ready,source_abstentions=value['requests']['abstained_source_rows'],
        forecasted_rows=0,model_pending_rows=len(ready),actual_model_consumer_executed=False)
