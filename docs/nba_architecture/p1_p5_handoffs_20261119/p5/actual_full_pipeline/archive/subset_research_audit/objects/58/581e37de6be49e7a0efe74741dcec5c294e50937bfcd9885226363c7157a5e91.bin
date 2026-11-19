"""Create-only raw capture. Capture does not authenticate or admit a source."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def capture(url, destination):
    """Retain actual HTTP body and clocks; never infer publication from HTTP Date."""
    path = Path(destination)
    path.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    receipt = dict(schema='nba-p1-raw-capture/1.0.0', url=url,
                   retrieval_started_at=started, source_published_at=None,
                   original_historical_available_at=None, admission='UNADMITTED',
                   correction_history_complete=None, predecessor_sha256=None)
    try:
        with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30) as response:
            raw = response.read()
            receipt.update(status=response.status, headers=dict(response.headers))
        receipt['retrieval_completed_at'] = datetime.now(timezone.utc).isoformat()
        with (path / 'body.raw').open('xb') as stream:
            stream.write(raw)
        receipt.update(raw_sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                       byte_domain='HTTP_RESPONSE_BODY_BYTES',
                       ingested_at=datetime.now(timezone.utc).isoformat())
    except HTTPError as error:
        raw = error.read()
        with (path / 'body.raw').open('xb') as stream:
            stream.write(raw)
        receipt.update(status=error.code, headers=dict(error.headers),
                       error=type(error).__name__ + ': ' + str(error),
                       raw_sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                       byte_domain='HTTP_ERROR_RESPONSE_BODY_BYTES',
                       retrieval_completed_at=datetime.now(timezone.utc).isoformat(),
                       ingested_at=datetime.now(timezone.utc).isoformat())
    except Exception as error:
        receipt.update(error=type(error).__name__ + ': ' + str(error),
                       retrieval_completed_at=datetime.now(timezone.utc).isoformat())
    with (path / 'receipt.json').open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    return receipt
