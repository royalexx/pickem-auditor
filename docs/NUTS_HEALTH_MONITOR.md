# Live NUTS health monitoring — Pick'em Auditor

**Scope:** Training runs *after market 0 (SOG)* in the frozen `week-20261102` campaign, starting with market 1, will load the independently pinned monitor overlay. The current SOG run is unchanged. The model code, historical inputs, priors, four-chain NUTS settings and convergence gates remain frozen.

This reporter augments the existing `NUTS_PROGRESS` line and `progress.json` with a `NUTS_HEALTH` JSON log every reporting interval (typically 45 seconds). It records **per chain**:

| Metric | Why it helps | Caveat |
|---|---|---|
| Posterior divergences | Flags geometry/integration failures | Warmup divergences are counted separately; zero divergences does not prove convergence |
| Maximum tree-depth hits | Identifies saturation at NUTS's trajectory limit | Count uses the sampler's explicit `reached_max_treedepth` flag |
| Last 100 posterior mean acceptance probability | Flags persistent acceptance substantially below the 0.99 target | Warns only after 100 posterior draws and acceptance below 0.89 |
| Latest adapted step size, maximum depth and tree size | Reveals tiny step sizes or expensive trajectories | Descriptive only; no universal safe cutoff |
| Provisional E-BFMI | Early warning for poor energy exploration | Computes from ≥200 posterior energy samples; below 0.3 warns; final ArviZ E-BFMI is authoritative |
| Nonfinite posterior energy | Detects invalid numerical values | Treated as investigation warning, never masked |
| Seconds since last chain draw | Detects a possibly hung sampler | Warns after 15 minutes *only for a chain that already started and is not finished* |
| Missing sampler stats | Detects monitoring incompatibility | Does not claim sampler failure |

Each `progress.json` keeps its existing `pymc_chain_progress_v1` schema and adds:

```json
{
  "health": {
    "schema": "nuts_online_diagnostics_v1",
    "diagnostic_status": "provisional_not_convergence_certification",
    "target_accept": 0.99,
    "chains": {"0": {"posterior_divergences": 0, "provisional_ebfmi": null, "warnings": []}},
    "warnings": [],
    "final_rhat_ess_bfmi_required": true
  }
}
```

The example above omits other chain fields. Real reports include all four chains. Online monitoring is **read-only** and retains O(1) summary memory per chain. It does not inspect posterior parameters, replace final R-hat/ESS, trigger retraining, or automatically cancel a sampler. Warnings should be investigated and corroborated with complete-sample diagnostics.

Offline tests:

```bash
python -m unittest discover -s tests -p 'test_precision_sampling_progress.py' -v
```

**Deployment now enabled for successor markets:** `.github/workflows/precision-full-markets.yml` stages and tests an exact, Git-blob-pinned `precision_sampling_progress.py` from the workflow's `main` checkout, **before** checking out the campaign's frozen `CODE_HEAD`. After frozen-code verification, it replaces only the progress reporter module for **indices 1–30**, not the model itself, and writes a `monitor_receipt.json` documenting both frozen model SHA and monitor blob SHA. The existing market-zero SOG run was launched before this workflow change and cannot be modified by it.

**Warnings are advisory only.** The reporter never intentionally raises or cancels based on health readings. If the telemetry or output file fails during sampling, the monitor disables itself, reports `NUTS_MONITOR_UNAVAILABLE` if possible, and sampling continues unchanged. Before a future run starts, an unexpected monitor digest or failed self-test blocks startup to avoid silently deploying unintended code; that is a deployment integrity failure, not a sampler-health-triggered cancellation. The next market is still queued **only if the previous fit succeeds** under the campaign's existing convergence gates. No automatic restart is added.

See PyMC's NUTS diagnostics: https://www.pymc.io/projects/docs/en/latest/api/generated/pymc.NUTS.html
