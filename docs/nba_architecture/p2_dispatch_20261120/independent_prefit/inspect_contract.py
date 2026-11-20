"""Read-only pre-fit inspection of accepted source and contract evidence."""
import hashlib
import json
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[4]
history=root/'docs/nba_architecture/p1_p5_handoffs_20261119/prospective_inputs'
summary_path=history/'summary-401910016/body.raw'
schedule_path=history/'schedule-9/body.raw'
summary=json.loads(summary_path.read_bytes())
schedule=json.loads(schedule_path.read_bytes())
competition=summary['header']['competitions'][0]
event=next(e for e in schedule['events'] if e['id']=='401910016')
athlete=summary['boxscore']['players'][0]['statistics'][0]['athletes'][0]
adr=root/'docs/nba_architecture/narrow_default_20261119/ADR.md'
result=dict(
    reviewed_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
    source_paths_and_sha256={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (summary_path,schedule_path,adr,root/'v2/nba_s_family/model.py')},
    accepted_ordinary_exposure_clause='\n'.join(adr.read_text().splitlines()[24:28]),
    sample_summary_status=competition['status'],
    sample_summary_competition_keys=sorted(competition),
    sample_summary_linescores=[dict(team_id=c['id'],linescores=c.get('linescores'))
        for c in competition['competitors']],
    sample_schedule_status=event['competitions'][0]['status'],
    sample_boxscore_stat_names=summary['boxscore']['players'][0]['statistics'][0]['names'],
    sample_boxscore_row=athlete,
    findings=[
        'Integer displayed MIN is not an exact seconds exposure witness.',
        'Summary competition.status has no period in this accepted real source sample.',
        'Schedule competition.status has period; summary competitors have linescores. A new reviewed join is needed.',
        'Historical summary athlete.position is metadata observed at capture; original game-time role is not authenticated.',
        'Accepted ordinary-exposure clause explicitly excludes zero and sub30seconds.',
    ],
    fit_performed=False,model_admission_granted=False)
print(json.dumps(result,indent=2,sort_keys=True))
