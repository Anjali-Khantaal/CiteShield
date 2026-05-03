from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


class LifecycleTracker:
    """Lifecycle tracker with JSONL durability and optional MLflow emission.

    JSONL is always written so local and CI runs do not require an MLflow server.
    If `tracking_uri` is set and `mlflow` is importable, the same params/metrics
    are also recorded to MLflow.
    """

    def __init__(
        self,
        *,
        tracking_uri: str | None = None,
        jsonl_path: str = "artifacts/lifecycle_runs.jsonl",
        experiment_name: str = "CiteShield",
    ) -> None:
        self.tracking_uri = tracking_uri
        self.jsonl_path = Path(jsonl_path)
        self.experiment_name = experiment_name

    def log_query_trace(
        self,
        *,
        request_id: str,
        tenant_id: str,
        route: str,
        embedding_backend: str,
        embedding_model_name: str,
        generator_backend: str,
        generator_model_name: str,
        top_k: int,
        retrieval_latency_ms: float,
        generation_latency_ms: float,
        retrieved_sources: list[str],
        citation_count: int,
        abstained: bool,
    ) -> None:
        params = {
            "tenant_id": tenant_id,
            "route": route,
            "embedding_backend": embedding_backend,
            "embedding_model_name": embedding_model_name,
            "generator_backend": generator_backend,
            "generator_model_name": generator_model_name,
            "retrieval_top_k": top_k,
        }
        metrics = {
            "retrieval_latency_ms": retrieval_latency_ms,
            "generation_latency_ms": generation_latency_ms,
            "citation_count": citation_count,
            "abstained": int(abstained),
            "retrieved_source_count": len(retrieved_sources),
        }
        tags = {
            "request_id": request_id,
            "event": "query_trace",
            "retrieved_sources": ",".join(retrieved_sources[:10]),
            "retrieved_sources_hash": _hash_list(retrieved_sources),
        }
        self._log_event(
            event_name="query_trace",
            params=params,
            metrics=metrics,
            tags=tags,
            payload={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "route": route,
                "retrieved_sources": retrieved_sources,
                "citation_count": citation_count,
                "abstained": abstained,
            },
        )

    def log_evaluation_run(
        self,
        *,
        params: dict[str, Any],
        metrics: dict[str, float | int],
        tags: dict[str, str] | None = None,
        artifacts: dict[str, str] | None = None,
    ) -> None:
        self._log_event(
            event_name="evaluation_run",
            params=params,
            metrics=metrics,
            tags={"event": "evaluation_run", **(tags or {})},
            payload={"artifacts": artifacts or {}},
            artifacts=artifacts,
        )

    def _log_event(
        self,
        *,
        event_name: str,
        params: dict[str, Any],
        metrics: dict[str, float | int],
        tags: dict[str, str],
        payload: dict[str, Any] | None = None,
        artifacts: dict[str, str] | None = None,
    ) -> None:
        mlflow_status = self._log_mlflow(
            event_name=event_name,
            params=params,
            metrics=metrics,
            tags=tags,
            artifacts=artifacts or {},
        )
        event = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "event": event_name,
            "params": params,
            "metrics": metrics,
            "tags": tags,
            "tracking_uri": self.tracking_uri,
            "backend": "jsonl",
            "mlflow_status": mlflow_status,
            **(payload or {}),
        }
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with self.jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")

    def _log_mlflow(
        self,
        *,
        event_name: str,
        params: dict[str, Any],
        metrics: dict[str, float | int],
        tags: dict[str, str],
        artifacts: dict[str, str],
    ) -> str:
        if not self.tracking_uri:
            return "disabled"

        try:
            import mlflow  # type: ignore[import-not-found]
        except Exception:
            return "unavailable"

        try:
            mlflow.set_tracking_uri(self.tracking_uri)
            mlflow.set_experiment(self.experiment_name)
            with _mlflow_run(mlflow, run_name=event_name):
                for key, value in params.items():
                    mlflow.log_param(key, _stringify_param(value))
                for key, value in metrics.items():
                    mlflow.log_metric(key, float(value))
                for key, value in tags.items():
                    mlflow.set_tag(key, value)
                for artifact_name, artifact_path in artifacts.items():
                    if Path(artifact_path).exists():
                        mlflow.log_artifact(artifact_path, artifact_path=artifact_name)
            return "logged"
        except Exception as exc:
            return f"error:{type(exc).__name__}"


def generator_model_name(*, generator_backend: str, gemini_model_name: str, openai_compatible_model: str) -> str:
    backend = generator_backend.strip().lower()
    if backend == "gemini":
        return gemini_model_name
    if backend == "openai_compatible":
        return openai_compatible_model
    return "extractive"


@contextmanager
def _mlflow_run(mlflow: Any, *, run_name: str) -> Iterator[None]:
    active_run = mlflow.active_run()
    if active_run is not None:
        with mlflow.start_run(run_name=run_name, nested=True):
            yield
        return

    with mlflow.start_run(run_name=run_name):
        yield


def _hash_list(values: list[str]) -> str:
    payload = "\n".join(values).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _stringify_param(value: Any) -> str | int | float | bool:
    if isinstance(value, str | int | float | bool):
        return value
    return json.dumps(value, sort_keys=True)
