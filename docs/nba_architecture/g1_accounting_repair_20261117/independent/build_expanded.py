from pathlib import Path
s=Path('/workspace/nba-remediation/scripts/nba_p6_raw_display_matrix_20261117.py').read_text()
s=s.replace("        for exact in exacts:","        credit_names={'points':'points','rebounds':'reboundsTotal','assists':'assists','threes':'threePointersMade','fgm':'fieldGoalsMade','fga':'fieldGoalsAttempted','fg3a':'threePointersAttempted','ftm':'freeThrowsMade','fta':'freeThrowsAttempted','oreb':'reboundsOffensive','dreb':'reboundsDefensive','steals':'steals','blocks':'blocks','turnovers':'turnovers','personal_fouls':'foulsPersonal'}\n        for hidden,raw_name in credit_names.items():\n            retained_stat='assists' if hidden!='assists' else 'rebounds'\n            raw_retained=credit_names[retained_stat]\n            for exact in exacts:")
a=s.index('            parts=exact[2:-1]');b=s.index('    totals=',a)
s=s[:a]+''.join('    '+line if line.strip() else line for line in s[a:b].splitlines(keepends=True))+s[b:]
s=s.replace("{'minutes':exact,'points':11,'reboundsTotal':0,'assists':0,'threePointersMade':0}","{'minutes':exact,raw_name:1,raw_retained:0}")
s=s.replace("stats={'threes':0} if subset else dict(points=11,rebounds=0,assists=0,threes=0)","stats={retained_stat:0} if subset else {retained_stat:0,hidden:1}")
s=s.replace("stat='threes' if subset else 'points'","stat=retained_stat")
s=s.replace("row=dict(exact_raw_clock=exact,","row=dict(hidden_credit=hidden,exact_raw_clock=exact,")
s=s.replace("'qa_source_commit=subprocess", "'qa_source_commit=subprocess")
s=s.replace("qa_source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=Path(__file__).resolve().parents[1]).decode().strip()","qa_source_origin='independently expanded from immutable matrix d1ca72f; new file raw hash identifies executed bytes'")
s=s.replace("NBA_P6_RAW_DISPLAY_CONSUMER_MATRIX_V1","NBA_P6_INDEPENDENT_ALL_RAW_CREDIT_MATRIX_V1")
Path('/workspace/nba-proof/independent/expanded_matrix.py').write_text(s)
