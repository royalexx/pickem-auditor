from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import ast,runpy,subprocess,sys,os
root=Path.cwd()
pool=root/"reports/v25_sog_source_cert_sprint/2026-11-13/signed_pr122_20261113T165907226991Z/original_signed_sources"
from v2.nhl_sog_history_refresh import load_current
day=datetime.now(ZoneInfo("America/Toronto")).date().isoformat()
try:
    _history,_receipt=load_current(pool,day=day,now=datetime.now(timezone.utc))
except ValueError:
    log=root/"reports"/("nhl_sog_history_prewarm_"+day+".log")
    with log.open("a") as out:
        _p=subprocess.run([sys.executable,str(root/"research/nhl_sog_history_prewarm.py")],
            cwd=root,env={**os.environ,"PYTHONPATH":str(root)},stdout=out,stderr=out,timeout=2900)
    print("HISTORY_PREWARM",log.read_text()[-6000:])
    if _p.returncode:raise RuntimeError("HISTORY_PREWARM_FAILED")
    _history,_receipt=load_current(pool,day=day,now=datetime.now(timezone.utc))
if _history["qualified_players"]==0:raise RuntimeError("NO_QUALIFIED_CURRENT_SIGNED_HISTORY")
print("CURRENT_SIGNED_HISTORY",_receipt,"qualified_players",_history["qualified_players"])
source=root/"research/nhl_sog_daily_gamma_poisson_research_v1_5.py"
ast.parse(source.read_text(encoding="utf8"),filename=str(source))
_result=runpy.run_path(str(source),run_name="__main__")
del _result
