"""Create explicitly SYNTHETIC NHL SOG P4 input archives, no original certification.

Used only to exercise the unchanged Gamma fitter and full-count artifact chain.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from v2.nhl_sog_p4_forecasts import BUNDLE_SCHEMA, canonical, sha256


def make_fixture(root, *, event_start="2027-01-01T00:00:00Z"):
    root=Path(root).resolve()
    root.mkdir(parents=True,exist_ok=True)
    own=[];peers=[]
    def obs(pid,j,sog,toi):
        datum={"schema":"v25_nhl_sog_observation_v1",
               "event_id":f"SYNTH_{pid}_{j}","player_id":pid,
               "position_group":"F","played":True,"toi_minutes":toi,
               "shots_on_goal":sog,"event_ended_at":"2026-11-14T04:00:00Z"}
        raw=canonical(datum)
        rel=f"synthetic_obs/{pid}_{j}.json"
        path=root/rel
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            if path.read_bytes()!=raw:raise ValueError("SYNTHETIC_ARCHIVE_MUTATED")
        else:
            with path.open("xb") as f:f.write(raw)
        return {"source_kind":"collector_observed_bytes","archive_path":rel,
                "content_sha256":sha256(raw),
                "source_url":"https://api-web.nhle.com/v1/gamecenter/synthetic-fixture",
                "received_at":"2026-11-15T12:00:00Z"}
    for j in range(8):
        own.append(obs("100001",j,(j+1)%5,15.0+j%3))
    for ip in range(20):
        for j in range(10):
            peers.append(obs(str(200000+ip),j,(ip+j)%6,11.5+j%5))
    b={"schema":BUNDLE_SCHEMA,"source_classification":"synthetic",
       "synthetic_fixture":True,"event_id":"SYNTHETIC_FUTURE_NHL_EVENT",
       "player_id":"100001","team_id":"AAA","opponent_id":"BBB",
       "position_group":"F","input_freeze_at":"2026-11-21T12:00:00Z",
       "event_start_at":event_start,
       "historical_availability_cutoff_at":"2026-11-16T00:00:00Z",
       "own_official_history":own,"peer_official_history":peers,
       "source_manifest_sha256":None,"flags":{}}
    raw=canonical(b)
    path=root/"synthetic_nhl_sog_p4_bundle.json"
    if path.exists():
        if path.read_bytes()!=raw:raise ValueError("SYNTHETIC_BUNDLE_MUTATED")
    else:
        with path.open("xb") as f:f.write(raw)
    return {"synthetic":True,"bundle":str(path),
            "bundle_sha256":sha256(raw),
            "own_played_games":8,"peer_players":20,"peer_played_games":200,
            "never_certified_original":True}


if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--root",required=True)
    a.add_argument("--event-start",default="2027-01-01T00:00:00Z")
    args=a.parse_args()
    print(json.dumps(make_fixture(args.root,event_start=args.event_start),indent=2))
