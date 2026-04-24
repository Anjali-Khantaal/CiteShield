from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class LifecycleTracker:
    """Lightweight lifecycle tracker with optional MLflow support.

    Always writes JSONL events so CI/local runs stay dependency-light.
    """

    def __init__(self, *, tracking_uri: str | None = None, jsonl_path: str = "artifacts/lifecycle_runs.jsonl") -> None:
        self.tracking_uri = tracking_uri
        self.jsonl_path = Path(jsonl_path)

    def log_evaluation_run(self, *, params: dict[str, Any], metrics: dict[str, float | int], tags: dict[str, str] | None = None) -> None:
        event = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "event": "evaluation_run",
            "params": params,
            "metrics": metrics,
            "tags": tags or {},
            "tracking_uri": self.tracking_uri,
            "backend": "jsonl",
        }
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with self.jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
