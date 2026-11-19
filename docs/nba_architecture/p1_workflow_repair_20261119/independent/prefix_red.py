"""Immutable public-function red at exact9352ae implementation; no source edits."""
import subprocess,json
code=subprocess.check_output(['git','show','9352ae0bb71dcc935327b1443856fe1e17102af3:v2/nba_architecture/p1_injury_report_v2.py']);namespace={'__name__':'v2.nba_architecture.review9352','__package__':'v2.nba_architecture'};exec(compile(code,'9352ae0b:p1_injury_report_v2.py','exec'),namespace)
u='https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-19_02_00PM.pdf.evil'
x=namespace['select_report'](('<a href="'+u+'">pdf</a>').encode(),observed_at='2026-11-19T19:10:00Z',freeze_at='2026-11-19T19:15:00Z');print(json.dumps(x,indent=2));assert x['selected_url'] is None,'malformed href was truncated into a never-indexed valid URL'
