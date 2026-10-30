#!/usr/bin/env python3
"""Auditable per-chain PyMC NUTS progress for self-hosted GitHub Actions.

The callback receives draws from the parent sampler even when chains are
multiprocess. GitHub doesn't reliably render Rich terminal progress bars,
so report a persistent JSON snapshot and periodic one-line ASCII bars.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


class NUTSProgress:
    def __init__(self, *, draws: int, tune: int, chains: int, output: Path,
                 sport: str, stat: str, interval_seconds: int = 45):
        self.total = draws + tune
        self.draws = draws
        self.tune = tune
        self.chains = chains
        self.output = Path(output)
        self.sport = sport
        self.stat = stat
        self.interval = max(2, interval_seconds)
        self.counts = {str(i): 0 for i in range(chains)}
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
        elapsed = round(time.monotonic() - self.started_at)
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
            "elapsed_seconds": elapsed,
            "checked_at_utc": datetime.now(timezone.utc).isoformat()
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
            self.stage = "warmup" if bool(draw.tuning) else "posterior_sampling"
            self.counts[chain] = max(self.counts[chain], int(draw.draw_idx) + 1)
            now = time.monotonic()
            if now - self.last_print >= self.interval or self.counts[chain] == self.total:
                self._emit("running")
                self.last_print = now

    def close(self, status="completed"):
        self.shutdown.set()
        self.heartbeat.join(timeout=2)
        with self.lock:
            self.stage = "done" if status == "completed" else "interrupted"
            self._emit(status)
