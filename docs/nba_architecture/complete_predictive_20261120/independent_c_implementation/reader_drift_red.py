"""d98a2443 public red: source parser file-byte drift is not bound by C root."""
from pathlib import Path
from unittest.mock import patch
import importlib.util,sys,json
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from v2.nba_architecture.conditional_c_v1 import read_native_outcomes
P=ROOT/'docs/nba_architecture/complete_predictive_20261120';s=importlib.util.spec_from_file_location('inputs',P/'inputs.py');i=importlib.util.module_from_spec(s);s.loader.exec_module(i);reader=ROOT/'v2/nba_architecture/prospective_s_sources_v1.py';original=Path.read_bytes;reads=[]
def drift(path):
 if path==reader:reads.append(str(path));return original(path)+b'\n# simulated changed parser file bytes\n'
 return original(path)
with patch.object(Path,'read_bytes',drift):
 try:r=read_native_outcomes(**i.outcome_inputs())
 except ValueError as e:print(json.dumps({'status':'REJECTED','reason':str(e),'parser_file_hash_reads':len(reads)}));raise SystemExit(0)
print(json.dumps({'status':'RED_SOURCE_READER_BYTE_DRIFT_NOT_REJECTED','rows_admitted':r['source_row_denominator'],'parser_file_hash_reads':len(reads),'simulation_domain':'Path.read_bytes parser-file byte drift; source and parser behavior untouched'}));raise SystemExit(1)
