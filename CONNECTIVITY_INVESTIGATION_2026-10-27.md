# API connectivity investigation — 2026-10-27

## Findings

- The restored `Pickem_Auditor_history.zip` contains October 26 actual NHL REST data, demonstrating a previously successful external collection.
- A neutral-domain DNS check and requests to `api-web.nhle.com`, `api.nhle.com`, `site.api.espn.com`, and `api.the-odds-api.com` fail **before HTTP**, with `gaierror: Temporary failure in name resolution`, from the current ChatGPT Python/container runtime.
- The condition persists when probing without any installed NHL/NFL/NBA libraries or API credentials, so it cannot be fixed through an endpoint or credential change within Python.
- The morning ChatGPT scheduled task recorded `no_update` and no collection receipt; this *does not prove the scheduled executor experienced the same DNS failure*. It may be a separate automation-execution limitation.

## Patches in this package

- `scripts/network_receipt.py` checks unauthenticated HTTPS transport and minimal schema for NHL and ESPN, and an unrelated control host. Its output explicitly says that **no collection was performed**. It sends no API keys.
- `scripts/jobs.py snapshot` emits `RUNTIME_DNS_UNAVAILABLE` if all HTTPS preflight failures are DNS failures, rather than treating it as empty slate.
- The optional GitHub Actions shadow workflow saves the network receipt even if later collection fails. This workflow must be deployed to a user's repository with permitted outbound internet and any required `ODDS_API_KEY` secret. Its calibration branch is **not** the ChatGPT Library historical archive.
- `tests/test_network_receipt.py` tests DNS, HTTP authentication, schema mismatch and truthful zero-collection reporting with mocked transports.

## Execution instructions

1. Run `python3 scripts/network_receipt.py --out data/collection_network_receipt.json` on the target executor. `RUNTIME_DNS_UNAVAILABLE` means the executor has no usable DNS path; changing the NHL/ESPN endpoint will not fix it.
2. If `ENDPOINT_PROBES_PASSED`, run `python3 scripts/fetch_slate.py --date YYYY-MM-DD --out data/slate_fetch.jsonl`. The network receipt itself never supplies player rows or model probabilities.
3. Verify `data/slate_fetch.jsonl`, `data/odds_quotes.jsonl`, feed statuses in the returned summary, and then archive ingestion/persistence. **Do not update the Library archive merely because a network check or task trigger succeeded.**
4. For reproducible scheduled collection, run in a network-enabled agent or deploy the included GitHub Actions workflow in a repository. The ChatGPT morning automation cannot be made network-enabled by editing a ZIP. If migrating historical data out of Library, implement/verify an explicit sync back into its canonical file identity; never claim GitHub branch persistence equals Library persistence.

## Safety and provenance

Do not ship `config/credentials.local.json` in an attachment or commit it to GitHub. Preserve the old history and all 1,492 pregame forecasts. Do not backdate fresh snapshots or create synthetic NHL rows from forecasts.
