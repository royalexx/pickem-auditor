"""Public CLI rejection receipts: synthetic attacks, never source evidence."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

PACK=Path(__file__).resolve().parent
REPO=PACK.parents[2]


def main():
    output=PACK/'public_attacks';output.mkdir(exist_ok=False)
    cases=('missing-roster-member','duplicate-identity','wrong-team','wrong-game','altered-official-bytes',
        'late-clock','unsupported-publication','orphan-correction','false-completeness')
    rows=[]
    for case in cases:
        evidence=output/case;evidence.mkdir()
        with tempfile.TemporaryDirectory(prefix='genuine-s-negative-') as temporary:
            temp=Path(temporary);raw=temp/'raw';shutil.copytree(PACK/'raw',raw)
            file='nba-box-0022600022/body.raw' if case=='altered-official-bytes' else 'scoreboard/body.raw' if case=='wrong-game' else 'roster-16/receipt.json' if case in ('late-clock','unsupported-publication','orphan-correction','false-completeness') else 'roster-16/body.raw'
            path=raw/file
            if case=='altered-official-bytes':path.write_bytes(path.read_bytes()+b' ')
            else:
                value=json.loads(path.read_bytes())
                if case=='missing-roster-member':value['athletes'].pop()
                if case=='duplicate-identity':value['athletes'].append(value['athletes'][0])
                if case=='wrong-team':value['team']['id']='9'
                if case=='wrong-game':
                    next(e for e in value['events'] if str(e['id'])=='401910026')['id']='401910019'
                if case=='late-clock':value['ingested_at']='2026-11-23T02:00:00Z'
                if case=='unsupported-publication':value['source_published_at']='2026-11-01T01:00:00Z'
                if case=='orphan-correction':value['predecessor_sha256']='0'*64
                if case=='false-completeness':value['correction_history_complete']=True
                path.write_text(json.dumps(value,sort_keys=True,separators=(',',':')))
            mutation=evidence/'mutated'/file;mutation.parent.mkdir(parents=True);shutil.copyfile(path,mutation)
            command=[sys.executable,'scripts/nba_genuine_s.py','forecast']
            inputs={'raw-dir':raw,'spec-path':PACK/'PREFIT_POPULATION.json','policy-path':PACK/'policy/nba_rule5.raw',
                'model-dir':PACK/'fitted','prefit-path':PACK/'independent_prefit/PREFIT_APPROVAL.json',
                'admission-path':PACK/'independent_artifacts/ARTIFACT_ADMISSION.json',
                'model-path':REPO/'research/nba_ws2/results/model.json','cohort-path':PACK/'COHORT.json','output':temp/'output'}
            for name,value in inputs.items():command.extend(['--'+name,str(value)])
            started=datetime.now(timezone.utc).isoformat()
            child=subprocess.run(command,cwd=REPO,capture_output=True,text=True)
            (evidence/'stdout').write_text(child.stdout);(evidence/'stderr').write_text(child.stderr)
            result=json.loads(child.stdout)
            assert child.returncode!=0 and result['rejected_rows']==result['attempt_denominator']==140
            assert result['candidate_denominator']==35 and result['forecasted_rows']==0
            assert not (temp/'output').exists()
            row=dict(case=case,mode='SYNTHETIC_MUTATION_OF_REAL_CAPTURE_NEGATIVE_ONLY',command=command,cwd=str(REPO),
                tested_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
                started_at=started,completed_at=datetime.now(timezone.utc).isoformat(),exit_code=child.returncode,
                input_reconstruction='Original immutable raw/ tree plus exact mutated/ overlay file; only the overlay is changed.',
                mutation_file=file,attempt_denominator=140,rejected_rows=140,forecasted_rows=0,
                error=result['error'],passed=True)
            (evidence/'COMMAND.json').write_text(json.dumps(row,indent=2)+'\n');rows.append(row)
    (output/'RESULTS.json').write_text(json.dumps(dict(cases=rows,passed=len(rows),failed=0),indent=2)+'\n')
    print(json.dumps(dict(passed=len(rows),failed=0)))


if __name__=='__main__':main()
