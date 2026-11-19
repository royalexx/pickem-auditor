"""Chronological NBA report selection. Filename clocks never prove publication."""
from datetime import datetime, timedelta, timezone
import hashlib
from html import unescape
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from .p1_capture_v1 import capture

VERSION='nba-injury-report-capture/2.0.0'
INDEX='https://official.nba.com/nba-injury-report-2026-27-season/'
TZ=ZoneInfo('America/New_York')


def instant(value):
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None:raise ValueError('TIMEZONE_REQUIRED')
    return dt.astimezone(timezone.utc)


def report_time(url):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.netloc!='ak-static.cms.nba.com' or parsed.query or parsed.fragment:
        raise ValueError('UNSUPPORTED_REPORT_URL')
    match=re.fullmatch(r'/referee/injury/Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{2})_(\d{2})(AM|PM)\.pdf',parsed.path)
    if not match:raise ValueError('UNSUPPORTED_REPORT_PATH')
    day,hour,minute,ampm=match.groups();hour=int(hour);minute=int(minute)
    if not 1<=hour<=12 or not 0<=minute<60:raise ValueError('INVALID_REPORT_CLOCK')
    naive=datetime.strptime(day,'%Y-%m-%d').replace(hour=hour%12+(12 if ampm=='PM' else 0),minute=minute)
    local=naive.replace(tzinfo=TZ)
    if local.utcoffset()!=naive.replace(tzinfo=TZ,fold=1).utcoffset():raise ValueError('AMBIGUOUS_OR_NONEXISTENT_REPORT_CLOCK')
    if local.astimezone(timezone.utc).astimezone(TZ).replace(tzinfo=None)!=naive:raise ValueError('NONEXISTENT_REPORT_CLOCK')
    return local.astimezone(timezone.utc)


def select_report(raw_index, *, observed_at, freeze_at, max_age_minutes=60):
    observed,freeze=instant(observed_at),instant(freeze_at)
    if observed>freeze:raise ValueError('INDEX_AFTER_FREEZE')
    if type(max_age_minutes) is not int or max_age_minutes<0:raise ValueError('INVALID_FRESHNESS_BOUND')
    # Preserve whole quoted href values: a PDF prefix inside a malformed URL
    # must not become a different, invented indexed source.
    hrefs=re.findall(r"""href\s*=\s*["'](https?://[^"']+)["']""",unescape(raw_index.decode('utf-8')),flags=re.I)
    urls=[u for u in hrefs if '.pdf' in u.lower()]
    ledger=[];eligible=[]
    for url in sorted(set(urls)):
        row={'url':url,'source_declared_report_at':None}
        try:
            clock=report_time(url);row['source_declared_report_at']=clock.isoformat()
            if clock>observed:row['status']='REJECTED_FUTURE_REPORT_CLOCK'
            elif observed-clock>timedelta(minutes=max_age_minutes):row['status']='REJECTED_STALE_REPORT_CLOCK'
            else:row['status']='ELIGIBLE_CLOCK_ONLY';eligible.append((clock,url))
        except ValueError as error:row['status']='REJECTED_UNSUPPORTED_OR_INVALID';row['reason']=str(error)
        ledger.append(row)
    selected=max(eligible)[1] if eligible else None
    return dict(schema=VERSION,index_raw_sha256=hashlib.sha256(raw_index).hexdigest(),
                observed_at=observed_at,input_freeze_at=freeze_at,max_age_minutes=max_age_minutes,
                url_occurrences=len(urls),unique_urls=len(ledger),ledger=ledger,selected_url=selected,
                eligible_urls=len(eligible),rejected_urls=len(ledger)-len(eligible),
                source_publication_at=None,admission='UNADMITTED')


def verify_report(pdf_path, expected_url):
    raw=Path(pdf_path).read_bytes()
    if not raw.startswith(b'%PDF-'):raise ValueError('PDF_BODY_REQUIRED')
    text=subprocess.check_output(['pdftotext','-f','1','-l','1',str(pdf_path),'-']).decode('utf-8')
    headers=re.findall(r'Injury Report:\s*(\d{2}/\d{2}/\d{2})\s+(\d{2}:\d{2})\s*(AM|PM)',text)
    if len(set(headers))!=1:raise ValueError('MISSING_OR_AMBIGUOUS_PRINTED_HEADER')
    day,clock,ampm=headers[0]
    expected=report_time(expected_url).astimezone(TZ)
    declared=datetime.strptime(day+' '+clock+' '+ampm,'%m/%d/%y %I:%M %p')
    if declared!=expected.replace(tzinfo=None):raise ValueError('PRINTED_HEADER_FILENAME_MISMATCH')
    return dict(raw_sha256=hashlib.sha256(raw).hexdigest(),printed_report_clock=declared.isoformat(),
                source_declared_report_at=expected.isoformat(),source_publication_at=None)


def capture_latest(*, freeze_at, output):
    """Actual public HTTP path; failure records all selected bytes without fallback."""
    instant(freeze_at);out=Path(output);out.mkdir(parents=True,exist_ok=False)
    result=dict(schema=VERSION,status='REJECTED',input_freeze_at=freeze_at,errors=[],admission='UNADMITTED')
    try:
        if datetime.now(timezone.utc)>=instant(freeze_at):raise ValueError('CAPTURE_STARTED_AFTER_FREEZE')
        index=capture(INDEX,out/'index');result['index_receipt']=index
        if index.get('status')!=200:raise ValueError('INDEX_HTTP_UNAVAILABLE')
        selection=select_report((out/'index/body.raw').read_bytes(),observed_at=index['ingested_at'],freeze_at=freeze_at)
        result['selection']=selection
        if not selection['selected_url']:raise ValueError('NO_FRESH_REPORT')
        report=capture(selection['selected_url'],out/'report');result['report_receipt']=report
        if report.get('status')!=200:raise ValueError('LATEST_REPORT_HTTP_UNAVAILABLE_NO_FALLBACK')
        result['printed_content']=verify_report(out/'report/body.raw',selection['selected_url'])
        if instant(report['ingested_at'])>instant(freeze_at):raise ValueError('REPORT_CAPTURE_AFTER_FREEZE')
        result['status']='CAPTURED_BOUNDED_UNADMITTED'
    except (ValueError,KeyError,OSError,UnicodeError,subprocess.CalledProcessError) as error:
        result['errors'].append(str(error))
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(out))+'\n' for p in sorted(out.rglob('*')) if p.is_file())
    (out/'SHA256SUMS').write_text(manifest)
    return result
