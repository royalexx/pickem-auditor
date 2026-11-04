#!/usr/bin/env python3
"""Low-overhead per-chain NUTS progress and *provisional* live diagnostics.

The parent-process callback receives PyMC Draw objects even with multiple
worker processes. Metrics are observational: never interrupt sampling, modify
adaptation, or declare convergence. Final R-hat/ESS/BFMI remain authoritative.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path


class _ChainHealth:
    """Online O(1) statistics; does not retain model parameters or draws."""

    def __init__(self):
        self.posterior_draws = 0
        self.warmup_draws = 0
        self.stats_observed = 0
        self.posterior_divergences = 0
        self.warmup_divergences = 0
        self.posterior_max_treedepth_hits = 0
        self.warmup_max_treedepth_hits = 0
        self.last_step_size = None
        self.last_depth = None
        self.max_depth = None
        self.max_tree_size = None
        self.max_abs_energy_error = None
        self.accept_count = 0
        self.accept_sum = 0.0
        self.accept_recent = deque(maxlen=100)
        self.energy_count = 0
        self.energy_mean = 0.0
        self.energy_m2 = 0.0
        self.last_energy = None
        self.energy_jump_count = 0
        self.energy_jump_sq_sum = 0.0
        self.nonfinite_posterior_energy = 0
        self.last_draw_at = None

    @staticmethod
    def _number(value):
        try:
            n = float(value)
        except (ValueError, TypeError, OverflowError):
            return None
        return n if math.isfinite(n) else None

    def observe(self, *, tuning: bool, stats, now: float):
        self.last_draw_at = now
        if tuning:
            self.warmup_draws += 1
        else:
            self.posterior_draws += 1
        if not isinstance(stats, dict):
            return
        self.stats_observed += 1
        if bool(stats.get("diverging", False)):
            if tuning:
                self.warmup_divergences += 1
            else:
                self.posterior_divergences += 1
        if bool(stats.get("reached_max_treedepth", False)):
            if tuning:
                self.warmup_max_treedepth_hits += 1
            else:
                self.posterior_max_treedepth_hits += 1
        step = self._number(stats.get("step_size"))
        if step is not None and step > 0:
            self.last_step_size = step
        depth = self._number(stats.get("depth"))
        if depth is not None and depth >= 0:
            self.last_depth = int(depth)
            self.max_depth = max(self.max_depth or 0, int(depth))
        size = self._number(stats.get("tree_size"))
        if size is not None and size >= 0:
            self.max_tree_size = max(self.max_tree_size or 0, int(size))
        error = self._number(stats.get("max_energy_error"))
        if error is not None:
            self.max_abs_energy_error = max(self.max_abs_energy_error or 0.0, abs(error))
        if tuning:
            # Burn-in adaptation statistics are NOT posterior health metrics.
            return
        accept = self._number(stats.get("mean_tree_accept"))
        if accept is not None and 0 <= accept <= 1:
            self.accept_count += 1
            self.accept_sum += accept
            self.accept_recent.append(accept)
        if "energy" in stats:
            energy = self._number(stats.get("energy"))
            if energy is None:
                self.nonfinite_posterior_energy += 1
                self.last_energy = None
                return
            self.energy_count += 1
            delta = energy - self.energy_mean
            self.energy_mean += delta / self.energy_count
            self.energy_m2 += delta * (energy - self.energy_mean)
            if self.last_energy is not None:
                gap = energy - self.last_energy
                self.energy_jump_sq_sum += gap * gap
                self.energy_jump_count += 1
            self.last_energy = energy

    def snapshot(self, now: float, *, complete: bool, target_accept: float,
                 stall_seconds: int):
        warnings = []
        accept = (self.accept_sum / self.accept_count if self.accept_count else None)
        recent = (sum(self.accept_recent) / len(self.accept_recent)
                  if self.accept_recent else None)
        # A *running* E-BFMI estimate is only a diagnostic hint, never an
        # automatic convergence pass/fail. It requires enough posterior energy.
        ebfmi = None
        if self.energy_count >= 200 and self.energy_jump_count >= 199:
            variance = self.energy_m2 / self.energy_count
            if variance > 0 and math.isfinite(variance):
                ebfmi = self.energy_jump_sq_sum / self.energy_jump_count / variance
        if self.posterior_divergences:
            warnings.append("posterior_divergence_detected")
        if self.posterior_max_treedepth_hits:
            warnings.append("posterior_treedepth_saturated")
        if self.posterior_draws >= 100 and recent is not None and recent < target_accept - 0.10:
            warnings.append("recent_acceptance_below_target")
        if ebfmi is not None and ebfmi < 0.3:
            warnings.append("provisional_low_ebfmi")
        if self.nonfinite_posterior_energy:
            warnings.append("nonfinite_posterior_energy")
        if self.warmup_draws + self.posterior_draws >= 50 and self.stats_observed == 0:
            warnings.append("nuts_callback_stats_missing")
        age = (max(0.0, now - self.last_draw_at) if self.last_draw_at is not None
               else None)
        if age is not None and not complete and age >= stall_seconds:
            warnings.append("active_chain_no_recent_draw")
        result = {
            "warmup_draws_observed": self.warmup_draws,
            "posterior_draws_observed": self.posterior_draws,
            "warmup_divergences": self.warmup_divergences,
            "posterior_divergences": self.posterior_divergences,
            "posterior_max_treedepth_hits": self.posterior_max_treedepth_hits,
            "posterior_acceptance_mean": round(accept, 4) if accept is not None else None,
            "recent_100_posterior_acceptance_mean": round(recent, 4) if recent is not None else None,
            "last_step_size": round(self.last_step_size, 9) if self.last_step_size is not None else None,
            "max_tree_depth_observed": self.max_depth,
            "max_tree_size_observed": self.max_tree_size,
            "max_abs_energy_error_observed": (round(self.max_abs_energy_error, 3)
                                              if self.max_abs_energy_error is not None else None),
            "provisional_ebfmi": round(ebfmi, 3) if ebfmi is not None else None,
            "posterior_energy_observations": self.energy_count,
            "seconds_since_last_draw": round(age) if age is not None else None,
            "activity": "completed" if complete else "not_started" if age is None else "active",
            "warnings": warnings,
        }
        return result


class NUTSProgress:
    def __init__(self, *, draws: int, tune: int, chains: int, output: Path,
                 sport: str, stat: str, interval_seconds: int = 45,
                 target_accept: float = 0.99, stall_seconds: int = 900):
        self.total = draws + tune
        self.draws = draws
        self.tune = tune
        self.chains = chains
        self.output = Path(output)
        self.sport = sport
        self.stat = stat
        self.interval = max(2, interval_seconds)
        self.target_accept = target_accept
        self.stall_seconds = max(30, stall_seconds)
        self.counts = {str(i): 0 for i in range(chains)}
        self.health = {str(i): _ChainHealth() for i in range(chains)}
        self.started_at = time.monotonic()
        self.last_print = self.started_at
        self.first_draw = False
        self.stage = "initializing_and_compiling"
        self.lock = threading.Lock()
        self.shutdown = threading.Event()
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self._emit("init")
        self.heartbeat = threading.Thread(target=self._heartbeat, daemon=True)
        self.heartbeat.start()

    def _state(self, status):
        completed = sum(self.counts.values())
        target = self.total * self.chains
        percent = 100.0 * completed / target
        now = time.monotonic()
        health = {}
        alerts = []
        for chain, stream in self.health.items():
            snapshot = stream.snapshot(now, complete=self.counts[chain] >= self.total,
                                       target_accept=self.target_accept,
                                       stall_seconds=self.stall_seconds)
            health[chain] = snapshot
            alerts.extend(f"chain_{chain}:{item}" for item in snapshot["warnings"])
        return {
            "schema": "pymc_chain_progress_v1",
            "status": status,
            "stage": self.stage,
            "sport": self.sport, "stat": self.stat,
            "chains": self.chains, "tune": self.tune,
            "posterior_draws_per_chain": self.draws,
            "iterations_per_chain": self.total,
            "completed_iterations": completed,
            "target_iterations": target,
            "percent": round(percent, 2),
            "per_chain_iterations": dict(self.counts),
            "elapsed_seconds": round(now - self.started_at),
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "health": {
                "schema": "nuts_online_diagnostics_v1",
                "diagnostic_status": "provisional_not_convergence_certification",
                "target_accept": self.target_accept,
                "chains": health,
                "warnings": alerts,
                "final_rhat_ess_bfmi_required": True,
            },
        }

    def _emit(self, status):
        item = self._state(status)
        temp = self.output.with_suffix(".tmp")
        temp.write_text(json.dumps(item, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, self.output)
        filled = min(24, int(item["percent"] * 24 / 100))
        bar = "#" * filled + "-" * (24 - filled)
        print(f"NUTS_PROGRESS sport={self.sport} stat={self.stat} "
              f"[{bar}] {item['percent']:5.1f}% "
              f"stage={item['stage']} chains={item['per_chain_iterations']} "
              f"elapsed={item['elapsed_seconds']}s status={status}", flush=True)
        telemetry = {
            chain: {
                "post": state["posterior_draws_observed"],
                "div": state["posterior_divergences"],
                "depth_hits": state["posterior_max_treedepth_hits"],
                "accept100": state["recent_100_posterior_acceptance_mean"],
                "ebfmi_prelim": state["provisional_ebfmi"],
                "step": state["last_step_size"],
                "max_depth": state["max_tree_depth_observed"],
                "last_draw_age_s": state["seconds_since_last_draw"],
                "activity": state["activity"],
            }
            for chain, state in item["health"]["chains"].items()
        }
        print("NUTS_HEALTH " + json.dumps({
            "sport": self.sport, "stat": self.stat, "chains": telemetry,
            "alerts": item["health"]["warnings"], "status": "provisional",
        }, sort_keys=True, separators=(",", ":")), flush=True)

    def _heartbeat(self):
        while not self.shutdown.wait(self.interval):
            with self.lock:
                if time.monotonic() - self.last_print >= self.interval:
                    self._emit("running")
                    self.last_print = time.monotonic()

    def __call__(self, *, trace, draw):
        chain = str(int(draw.chain))
        if chain not in self.counts:
            raise ValueError("unexpected_sampling_chain_index")
        with self.lock:
            self.first_draw = True
            tuning = bool(draw.tuning)
            self.stage = "warmup" if tuning else "posterior_sampling"
            self.counts[chain] = max(self.counts[chain], int(draw.draw_idx) + 1)
            stats = None
            raw_stats = getattr(draw, "stats", None)
            if isinstance(raw_stats, (list, tuple)):
                for entry in raw_stats:
                    if isinstance(entry, dict) and any(
                            key in entry for key in ("diverging", "depth", "mean_tree_accept")):
                        stats = entry
                        break
            elif isinstance(raw_stats, dict):
                stats = raw_stats
            now = time.monotonic()
            self.health[chain].observe(tuning=tuning, stats=stats, now=now)
            if now - self.last_print >= self.interval or self.counts[chain] == self.total:
                self._emit("running")
                self.last_print = now

    def close(self, status="completed"):
        self.shutdown.set()
        self.heartbeat.join(timeout=2)
        with self.lock:
            self.stage = "done" if status == "completed" else "interrupted"
            self._emit(status)
