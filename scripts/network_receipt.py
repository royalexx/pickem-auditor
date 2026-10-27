#!/usr/bin/env python3
"""Distinguish sandbox DNS/HTTPS restrictions from provider, schema, and key failures.

No API keys are transmitted or printed. Safe to run ahead of a collection. An
endpoint-only successful probe never constitutes a completed collection.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import socket
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINTS = {
    'control': ('www.google.com', 'https://www.google.com/', None),
    'nhl_schedule': ('api-web.nhle.com', 'https://api-web.nhle.com/v1/schedule/now', 'gameWeek'),
    'nhl_statistics': ('api.nhle.com', 'https://api.nhle.com/stats/rest/en/team?limit=1', 'data'),
    'espn_scoreboard': ('site.api.espn.com', 'https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard', 'events'),
    'odds_transport': ('api.prop-line.com', 'https://api.prop-line.com/v1/freshness', None),
}

def _error_kind(err: BaseException) -> str:
    if isinstance(err, socket.gaierror):
        return 'dns_unavailable'
    if isinstance(err, (socket.timeout, TimeoutError)):
        return 'timeout'
    if isinstance(err, ConnectionError):
        return 'connection_unavailable'
    if isinstance(err, urllib.error.URLError):
        if isinstance(err.reason, BaseException):
            return _error_kind(err.reason)
        return 'https_unavailable'
    return 'https_unavailable'

def probe(name: str, entry, *, timeout: float = 5, resolver=None, opener=None, proxies=None):
    host, url, expected_key = entry
    resolve = resolver or socket.getaddrinfo
    open_url = opener or urllib.request.urlopen
    dns_error = None
    try:
        resolve(host, 443, type=socket.SOCK_STREAM)
    except Exception as exc:
        dns_error = exc
        # With an HTTPS proxy the proxy may resolve origin domains itself.
        if not (proxies if proxies is not None else urllib.request.getproxies()).get('https'):
            return {'name':name, 'host':host, 'state':_error_kind(exc), 'reachable':False,
                    'error_type':type(exc).__name__}
    try:
        request = urllib.request.Request(url, headers={'User-Agent':'pickem-auditor-network-check/1', 'Accept':'application/json'})
        with open_url(request, timeout=timeout) as result:
            status = getattr(result, 'status', 200)
            if expected_key:
                body = result.read(2_000_000)
                try:
                    payload = json.loads(body)
                except (UnicodeDecodeError, ValueError):
                    return {'name':name, 'host':host, 'state':'invalid_json', 'reachable':True, 'http_status':status}
                if not isinstance(payload,dict) or expected_key not in payload:
                    return {'name':name,'host':host,'state':'schema_mismatch', 'reachable':True,'http_status':status}
            return {'name':name, 'host':host, 'state':'ok', 'reachable':True, 'http_status':status}
    except urllib.error.HTTPError as exc:
        state = {401:'authentication_required',403:'access_forbidden',429:'rate_limited'}.get(exc.code, 'http_error')
        exc.close()
        return {'name':name,'host':host,'state':state,'reachable':True,'http_status':exc.code}
    except Exception as exc:
        kind = _error_kind(exc)
        return {'name':name,'host':host,'state':kind,'reachable':False,'error_type':type(exc).__name__,
                **({'local_dns_error':type(dns_error).__name__} if dns_error else {})}

def diagnose(items: list[dict]) -> str:
    if not items:
        return 'not_checked'
    if all(item['state'] == 'dns_unavailable' for item in items):
        return 'RUNTIME_DNS_UNAVAILABLE'
    if not any(item.get('reachable') for item in items):
        return 'RUNTIME_EGRESS_UNAVAILABLE'
    if any(item['state']=='ok' for item in items) and any(not item.get('reachable') for item in items):
        return 'PARTIAL_NETWORK_FAILURE'
    if any(item['state'] in ('schema_mismatch','invalid_json') for item in items):
        return 'PROVIDER_SCHEMA_FAILURE'
    if any(item['state'] in ('rate_limited','authentication_required','access_forbidden') for item in items):
        return 'PROVIDER_AUTH_OR_QUOTA_FAILURE'
    if all(item['state']=='ok' for item in items):
        return 'ENDPOINT_PROBES_PASSED'
    return 'HTTP_ACCESS_OR_PROVIDER_FAILURE'

def run(timeout=5, endpoints=None, probe_fn=None):
    endpoints = endpoints or ENDPOINTS
    def check(pair):
        name, entry = pair
        return (probe_fn or probe)(name, entry, timeout=timeout)
    with ThreadPoolExecutor(max_workers=min(8,len(endpoints))) as executor:
        checks=list(executor.map(check, endpoints.items()))
    diagnosis=diagnose(checks)
    return {'checked_at':datetime.now(timezone.utc).isoformat(), 'diagnosis':diagnosis,
            'probes':checks, 'collection_performed':False, 'rows_collected':0,
            'note':'Checks network only, never approves tiers or establishes archive persistence.'}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout',type=float,default=5)
    parser.add_argument('--out',help='write JSON to a diagnostics artifact')
    args=parser.parse_args(argv)
    report=run(timeout=args.timeout)
    message=json.dumps(report,indent=2)+'\n'
    if args.out:
        path=Path(args.out)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(message)
    print(message,end='')
    return 0 if report['diagnosis']=='ENDPOINT_PROBES_PASSED' else 2

if __name__=='__main__':
    raise SystemExit(main())
