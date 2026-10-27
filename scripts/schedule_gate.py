#!/usr/bin/env python3
"""Map an Actions UTC cron occurrence to the intended Toronto-local job.

During DST the alternate UTC occurrence must be skipped. Delayed scheduled
jobs use the *planned* UTC hour/minute rather than the execution wall clock.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo('America/Toronto')
VALID_JOBS = {'snapshot', 'closing', 'settle', 'weekly'}

def scheduled_job(cron: str, now: datetime | None = None) -> str:
    if not cron:
        return 'skip'
    parts = cron.strip().split()
    if len(parts) != 5:
        return 'skip'
    try:
        minute, hour = int(parts[0]), int(parts[1])
    except ValueError:
        return 'skip'
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    planned = reference.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if planned > reference + timedelta(minutes=2):
        planned -= timedelta(days=1)
    if reference - planned > timedelta(hours=12):
        return 'skip'  # missing or severely delayed event, fail closed
    local = planned.astimezone(EASTERN)
    if (local.hour, local.minute) in {(9, 0), (14, 0)}:
        return 'snapshot'
    if (local.hour, local.minute) == (18, 55):
        return 'closing'
    if (local.hour, local.minute) == (3, 30):
        return 'settle'
    if local.weekday() == 0 and (local.hour, local.minute) == (5, 0):
        return 'weekly'
    return 'skip'

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--schedule', default='')
    parser.add_argument('--manual', default='')
    args = parser.parse_args()
    if args.manual:
        if args.manual not in VALID_JOBS:
            parser.error('invalid manually selected job')
        print(args.manual)
    else:
        print(scheduled_job(args.schedule))

if __name__ == '__main__':
    main()
