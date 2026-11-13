# C03 live provenance update — 2026-11-13 (research gate only)

**Source branch:** work/v25-c03-context-cohorts. Governing plan PA-V25-MASTER-2026-11-09/v1.1.
**Implemented:** scripts/c03_live_transport.py signs *collector TLS response body*
receipts in a separate immutable archive with HMAC-SHA256 keyed via
PICKEM_C03_COLLECTOR_HMAC_KEY_HEX (exactly 32 bytes, hex). The signed body
contains original URL **including event query**, source namespace, SHA-256
of raw body, observed/received UTC and collector-possession-only semantics.
Independent verifier checks BOTH raw bytes and signed receipt bytes, refuses
modified clocks/identity/missing secret or unsigned metadata flags.

scripts/c03_pregame_live_capture.py calls actual HTTPS transport when the
research-only C03 flag is explicitly set, extracts exact raw pregame ESPN
roster active/out bool via JSON pointer; team and athlete identity and
ESPN event ID must match. The functions do not infer a status when a player
is missing. A status report from other source schemas remains uncertified
until its own exact original value mapping is implemented.

scripts/jobs.py wires the opt-in hook and preserves the initial prepared
candidate before research merge. Explicitly **blocks any context-neutral
Cohort B forecast from entering production selections, rankings, snapshots or
publication**, even when the research flag was enabled. Rejections continue
in the all-attempt denominator.

**Not completed/verified:**
1. No live source body fetched and signed using a real collector-held secret
   in this execution. Tests use fixture bodies and a test key, not a live
   authoritative response. HMAC proves integrity under collector key trust,
   not upstream publication time. Independent runner/key protection audit
   and an actual source-source negative-control run remain required.
2. Current Propline event IDs must not be interpreted as ESPN event IDs;
   C03_ESPN_EVENT_CROSSWALK_UNVERIFIED is an explicit abstention. ESPN
   athlete IDs must likewise be crosswalk-certified; current prepared
   records may not declare a verified player ID namespace.
3. NHL roster membership is distinct from starting goalie / participation;
   official two-team roster evidence and appropriate named starting evidence
   remain mandatory. NFL named QB starter requires a separate authoritative
   report; passing the raw ESPN status boolean alone does not prove starter.
4. Contract-specific DNP/void status remains distinct from forecast
   conditional on player actually participating. No market settlement
   behavior is promoted from a generic status receipt.
5. An independent signer vs verifier trust-model review (including key
   rotation, operator access, archive atomicity) and real integration
   canary are needed before any Cohort B certified output is authorized.

**Safest next action:** establish approved canonical Propline↔ESPN
event/player crosswalk with original source receipts and a read-only
trusted collector environment. Then execute a live, timestamped,
authenticated body capture before an upcoming game, with independent
source verification. Current branch is shadow-only and draft; no schedules,
NUTS, tiers or publishing policy were modified.
