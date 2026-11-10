"""Matched decision card from frozen replay bytes; no retraining/tuning."""
from __future__ import annotations
import argparse,gzip,json
from collections import defaultdict
from pathlib import Path
from v25_opportunity_repair_replay import read,write_once,metrics,paired,probability_score

def build(folder,audit_export):
    report=read(folder/"FINAL_REPAIR_REPORT.json")
    ledger=read(folder/"RESEARCH_SCORED_LEDGER.json.gz")
    original=read(audit_export)
    key=lambda r:(r["week"],r["game_id"],r["team"],r["player_id"],r.get("market"),r.get("line",r.get("research_line")))
    index={key(r):r for r in original["rows"]}
    out={"schema":"v25-opportunity-repair-decision-v1","source_receipt":report["receipt_sha256"],
       "research_default":"simple_control","default_count_markets_only":True,
       "yard_replacement_authorized":False,"production_authorized":False,
       "decision_selected_on_development_exposed_2024":True,"markets":{}}
    for market in report["markets"]:
        new=ledger["simple_control|raw|"+market]
        old=[]
        for row in new:
            base=index[key(row)]
            if base["actual"] is None:raise AssertionError("missing_matched_baseline_actual")
            r={**row,"mean":base["simulated_mean"],"bias":base["simulated_mean"]-row["actual"],
               "mae":abs(base["simulated_mean"]-row["actual"]),"crps":None,"coverage80":None,"p_zero":None}
            if row["y"] is not None:r.update(probability_score(base["p_over"],row["y"]))
            old.append(r)
        out["markets"][market]={"n":len(new),"old_matched":metrics(old),"new_matched":metrics(new),
           "new_minus_old_brier":paired(new,old,"brier"),"new_minus_old_bias":paired(new,old,"bias"),
           "role_calibrated_new":report["markets"][market]["models"]["simple_control"]["role"],
           "decision":"research_count_default" if "yards" not in market else "retain_legacy_yards_candidate_only"}
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--folder",type=Path,required=True)
    p.add_argument("--audit-export",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();r=build(a.folder,a.audit_export);write_once(a.output,r)
    print(json.dumps({m:{"n":v["n"],"old_brier":v["old_matched"]["brier"],"new_brier":v["new_matched"]["brier"],"old_bias":v["old_matched"]["bias"],"new_bias":v["new_matched"]["bias"],"decision":v["decision"]} for m,v in r["markets"].items()},sort_keys=True))

if __name__=="__main__":main()
