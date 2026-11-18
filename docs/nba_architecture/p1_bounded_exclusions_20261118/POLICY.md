# Preregistered bounded historical demonstration 1.0.0

Authority PA-V25-MASTER-2026-11-09 / v1.1. Parent PR177 exact77fbc4b2.
Keep the frozen 26-row prior completed-game cohort and later target unchanged.
Apply exclusions after whole-source admission, before producing demonstration.
No deletion can repair corrupt/unadmitted sources or unknown roster completeness.

Include ordinary PLAYED rows with integer exact_seconds >=30 and no greater than
admitted full-game duration. Quarantine PLAYED_ZERO_MINUTES, positive exposures
below30seconds, missing/invalid exposure and unknown states as EXCLUDED with
reason. Keep explicit DNP separately (not exposure observations). Preserve every
input row and identity; input = included + DNP + excluded. No source-specific
rounded-display rule, positive-credit true-zero adjudication or DNP imputation.
This threshold deliberately avoids the sub30second exception boundary; it is a
conservative demonstration rule, not an inferred provider rounding convention.

Reported outcome: whether ordinary listed-game exposure/content can be read
under this restricted policy. No fit, forecast, scoring or target eligibility
claim. If actual admitted data contains zero exclusions, report zero; never
invent an outlier to make the test seem useful. Mutation fixtures test policy
boundaries separately from authentic source admission.

B-P1-01/B-P1-02 remain BLOCKED under original criteria. This policy changes no
original gate. Unknown roster/availability/clocks/corrections remain unknown.
Independent review must assess policy and actual public execution before final
acceptance. Rollback: discard this isolated branch; all old readers/roots and
prior evidence stay byte-identical.
