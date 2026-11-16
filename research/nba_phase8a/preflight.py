"""Read-only local readiness check; does not claim or consume capture slots."""
import importlib.metadata,json,shutil,subprocess,sys
from pathlib import Path
from research.nba_phase7.pilot import registered_slots,window_state,REGISTRY_SHA
from research.nba_phase7.participation import MODEL_HASH
from v2.nba_ws1.capture import now
from v2.nba_joint.common import sha

def check(output='reports/nba_phase7_pilot'):
    slots=registered_slots();at=now();pdf=shutil.which('pdftotext')
    if not pdf:raise ValueError('PDF_RUNTIME_UNAVAILABLE')
    version=subprocess.check_output([pdf,'-v'],stderr=subprocess.STDOUT,text=True,timeout=10)
    model=json.loads(Path('research/nba_joint_v01/results/model.json').read_text())
    if sha(model)!=MODEL_HASH:raise ValueError('FROZEN_MODEL_CHANGED')
    return dict(checked_at=at,python=sys.version,packages={p:importlib.metadata.version(p) for p in ('numpy','scipy')},pdftotext=pdf,poppler_version=version.splitlines()[0],registration_sha256=REGISTRY_SHA,model_sha256=MODEL_HASH,
        slots=[dict(slot=s['slot'],game_id=s['game']['game_id'],state=window_state(s,at),claim_exists=(Path(output)/('slot_%02d_'%s['slot']+s['game']['game_id'].split(':')[-1])/'ACQUISITION_CLAIM.json').exists()) for s in slots],network='requires game-day source recheck',storage='exclusive local writes; not WORM; archive originals after each attempt',scheduler=False)
if __name__=='__main__':print(json.dumps(check(),indent=2))
