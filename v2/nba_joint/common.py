from datetime import datetime, timezone
import hashlib
import json
import numpy as np

VERSION = 'NBAJointForecast/1.0.0'
STATS = ('points','rebounds','assists','threes','pr','pa','ra','pra')


def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=False)


def sha(obj): return hashlib.sha256(canonical(obj).encode()).hexdigest()


def instant(s):
    d=datetime.fromisoformat(s.replace('Z','+00:00'))
    if d.tzinfo is None:raise ValueError('NAIVE_TIMESTAMP')
    return d.astimezone(timezone.utc)


def rng_for(seed, game, scenario, stage):
    h=hashlib.sha256(f'{seed}/{game}/{scenario}/{stage}'.encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8],'little'))


def combos(stats):
    p,r,a=(stats[k] for k in STATS[:3])
    stats.update(pr=p+r,pa=p+a,ra=r+a,pra=p+r+a)
    return stats
