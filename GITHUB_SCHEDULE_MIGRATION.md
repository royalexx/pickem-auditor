# GitHub automation transition (October 27, 2026)

Scheduled in .github/workflows/pickem-daily.yml at Toronto 06:00 and 16:00
with DST-aware UTC cron filtering; also supports manual workflow_dispatch.

Morning: official NHL completed-game boxscores, multi-sport NBA/NHL/NFL
historical/roster slate, settlement of preexisting verified pregame forecasts.

Afternoon: updated NHL boxscores, multi-sport slate and time-stamped Engine
A/B shadow analysis ONLY with a valid PROPLINE_API_KEY Actions repository secret.
A shadow result is not an official graded pick and still requires sourcing.

Persistence: official NHL gamecenter boxscore files committed on main;
forecast snapshots stored through scripts/shadow_store.sh on a separate
data/shadow-calibration branch. A receipt artifact describes stage failures;
the final step fails an incomplete run.

Important limitations:
- The original October 26 history was losslessly migrated to data/history-archive and is restored on the first calibration run. Preserve its original pregame estimates.
- Broader NBA/NFL raw historical-source archival is not complete; temporary
  slate collection files and 90-day Actions artifacts are not durable history.
- Missing PROPLINE_API_KEY must be added through GitHub repository Settings >
  Secrets and variables > Actions > New repository secret. Never commit keys.
- Failed sources and missing history are never reported as a successful
  collection. Check the workflow conclusion AND the JSON receipt.
- Separate NHL-only workflow is now manual-only to prevent scheduled overlap.
