"""Bounded official NBA gamebook extraction, modern retrieval clocks retained.

The final box is distinct from quarter/half boxes. Parsed text never substitutes
for the PDF hash. Missing correction history and original availability stay null.
No roster for a future target game, predictive fit or admission is inferred.
"""
from fractions import Fraction
import hashlib
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from .v2_contracts import req, instant

VERSION='nba-official-gamebook-reader/1.0.0'
KEYS=('fgm','fga','threes','fg3a','ftm','fta','oreb','dreb','rebounds',
      'assists','personal_fouls','steals','turnovers','blocks','plus_minus','points')


def read_final_box(raw,receipt):
    req(type(raw) is bytes and raw.startswith(b'%PDF-'),'GAMEBOOK_PDF_REQUIRED')
    req(hashlib.sha256(raw).hexdigest()==receipt['raw_sha256'],'GAMEBOOK_RAW_HASH')
    url=urlsplit(receipt['url'])
    m=re.fullmatch(r'/pdfs/(\d{8})/\1_([A-Z]{6})_book.pdf',url.path)
    req(url.scheme=='https' and url.netloc=='statsdmz.nba.com' and not url.query and
        not url.fragment and m is not None and receipt['status']==200,'GAMEBOOK_OFFICIAL_CAPTURE')
    instant(receipt['retrieved_at'])
    with tempfile.TemporaryDirectory() as tmp:
        pdf=Path(tmp)/'game.pdf';pdf.write_bytes(raw)
        text=subprocess.check_output(['pdftotext','-layout','-f','1','-l','1',str(pdf),'-']).decode('utf-8')
    req('OFFICIAL SCORER' in text and 'FINAL BOX' in text,'GAMEBOOK_FINAL_BOX_REQUIRED')
    team=None;rows=[];totals=[];inactive=[];score_period=None
    for line in text.splitlines():
        if line.startswith('VISITOR:'):team=m[2][:3]
        elif line.startswith('HOME:'):team=m[2][3:]
        if line.startswith('Inactive:'):inactive.append(line)
        if line.startswith('SCORE BY PERIOD'):
            score_period=line.split()[3:];continue
        if not team:continue
        # Exactly16 credited integers follow the exact mm:ss source exposure.
        r=re.fullmatch(r'\s*(\d+)\s+(.+?)\s+(?:(?:F|C|G)\s+)?(\d{1,2}):(\d{2})\s+((?:-?\d+\s+){15}-?\d+)\s*',line)
        d=re.fullmatch(r"\s*(\d+)\s+(.+?)\s+DNP\s*-\s*(.+)",line)
        t=re.match(r'\s*(\d{3}):(\d{2})\s+',line)
        if r:
            seconds=int(r[3])*60+int(r[4]);req(int(r[4])<60,'GAMEBOOK_SECONDS')
            values=list(map(int,r[5].split()));stats=dict(zip(KEYS,values))
            req(all(v>=0 for k,v in stats.items() if k!='plus_minus'),'GAMEBOOK_COUNT_SUPPORT')
            req(stats['points']==2*(stats['fgm']-stats['threes'])+3*stats['threes']+stats['ftm'] and
                stats['threes']<=stats['fgm']<=stats['fga'] and stats['threes']<=stats['fg3a']<=stats['fga'] and
                stats['ftm']<=stats['fta'] and stats['rebounds']==stats['oreb']+stats['dreb'],'GAMEBOOK_COUNT_ACCOUNTING')
            rows.append(dict(team=team,jersey=r[1],name=r[2].strip(),state='PLAYED' if seconds else 'PLAYED_ZERO_MINUTES',
                exact_seconds=seconds,exact_minutes=str(Fraction(seconds,60)),stats=stats))
        elif d:rows.append(dict(team=team,jersey=d[1],name=d[2].strip(),state='DNP',reason=d[3],exact_seconds=None,exact_minutes=None,stats={}))
        elif t:
            values=line[t.end():].split()
            req(len(values)==16 and all(re.fullmatch(r'-?\d+',v) for v in values),'GAMEBOOK_TOTAL_COLUMNS')
            totals.append(dict(team=team,minutes=int(t[1])+Fraction(int(t[2]),60),stats=dict(zip(KEYS,map(int,values)))))
        elif re.match(r'\s*\d+\s+[^\d]',line):
            req(False,'GAMEBOOK_UNPARSED_PLAYER_ROW')
    req(len(totals)==2 and {t['team'] for t in totals}=={m[2][:3],m[2][3:]} and totals[0]['minutes']==totals[1]['minutes'],'GAMEBOOK_TEAM_DURATION')
    duration=totals[0]['minutes']/5;ot=(duration-48)/5
    req(ot.denominator==1 and ot>=0,'GAMEBOOK_OVERTIME_DURATION')
    req(score_period is not None and score_period[-1]=='FINAL' and len(score_period)==5+int(ot),'GAMEBOOK_PERIOD_DURATION_JOIN')
    req(len({(r['team'],r['jersey']) for r in rows})==len(rows) and len(rows)>=10,'GAMEBOOK_ROW_POPULATION')
    for total in totals:
        team=total['team']
        for key,value in total['stats'].items():
            if key!='plus_minus':req(sum(r['stats'].get(key,0) for r in rows if r['team']==team)==value,'GAMEBOOK_TEAM_STAT_TOTAL')
        # Printed gamebook seconds can have a one-second display reconciliation.
        req(abs(sum(r['exact_seconds'] or 0 for r in rows if r['team']==team)-duration*300)<=len(rows), 'GAMEBOOK_PLAYER_MINUTE_SUM')
    return dict(schema=VERSION,source_raw_sha256=receipt['raw_sha256'],url=receipt['url'],
        retrieved_at=receipt['retrieved_at'],source_domain='ORIGINAL_PDF_BYTES',
        game_date=m[1],teams=[m[2][:3],m[2][3:]],duration_minutes=str(duration),
        overtime_periods=int(ot),rows=rows,inactive_text=inactive,
        identity_scope='SOURCE_NAME_JERSEY_TEAM_NO_EXTERNAL_ID_CROSSWALK',
        original_available_at=None,correction_history_complete=None,
        source_admission='INDEPENDENT_REVIEW_REQUIRED',certification='HISTORICAL_RECONSTRUCTION_UNCERTIFIED')
