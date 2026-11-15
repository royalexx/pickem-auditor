"""Bounded official-source availability probe, never historical certification."""
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import gzip
from dataclasses import asdict
from v2.nba_ws1.store import Receipt
from v2.nba_joint.forecast import freeze


def main():
    root=Path('research/nba_phase6/official_source_probe');root.mkdir(parents=True,exist_ok=False)
    probes=[]
    urls=[('league_schedule','https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json'),
          ('official_injury_page','https://official.nba.com/nba-injury-report-2026-27-season/'),
          ('league_transactions','https://www.nba.com/players/transactions')]
    for kind,url in urls:
        item=dict(kind=kind,url=url,used_for_model=False,source_certified_eligibility=False)
        try:
            with urlopen(Request(url,headers={'User-Agent':'pickem-phase6-source-audit/1'}),timeout=15) as response:
                raw=response.read(4*1024*1024+1);item['http_status']=response.status;item['content_type']=response.headers.get('Content-Type')
            if len(raw)>4*1024*1024:raise ValueError('BOUNDED_SOURCE_SIZE_EXCEEDED')
            receipt=Receipt.capture(raw,source=url,observed_at=datetime.now(timezone.utc).isoformat(),origin='original_capture')
            filename=receipt.raw_sha256+'.gz';(root/filename).write_bytes(gzip.compress(raw,mtime=0))
            item.update(receipt=asdict(receipt),path=filename,bytes=len(raw),status='retrieved_unparsed_no_certification')
        except Exception as exc:item.update(status='blocked',error=type(exc).__name__,detail=str(exc))
        probes.append(item)
    freeze(root/'receipt.json',dict(probes=probes,interpretation='Current retrieval only. No historical publication clock or complete game-active player contract inferred; no new collector or automation.'))

if __name__=='__main__':main()
