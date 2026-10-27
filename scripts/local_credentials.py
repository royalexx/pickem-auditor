"""Operator configuration only; never include credentials in model/research output."""
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def odds_api_key(*,root=None,environ=None):
    env=os.environ if environ is None else environ
    # Explicitly empty also overrides the file, allowing offline/disabled runs.
    if 'ODDS_API_KEY' in env:
        return str(env['ODDS_API_KEY']).strip()
    path=Path(root or ROOT)/'config'/'credentials.local.json'
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:return ''
    except (OSError,ValueError):raise ValueError('Cannot read local credentials configuration') from None
    if not isinstance(data,dict) or set(data)-{'ODDS_API_KEY'}:
        raise ValueError('Local credentials configuration accepts only ODDS_API_KEY')
    value=data.get('ODDS_API_KEY','')
    if not isinstance(value,str) or any(ch.isspace() for ch in value.strip()):
        raise ValueError('Invalid ODDS_API_KEY in local credentials configuration')
    return value.strip()
