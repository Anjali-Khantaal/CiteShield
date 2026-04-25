import os
import sys
from time import sleep, monotonic

import httpx

BASE_URL = os.getenv("CITESHIELD_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
TENANT_KEY = os.getenv("CITESHIELD_TENANT_API_KEY", os.getenv("TENANT_A_API_KEY", "tenant-a-dev-key"))
REQUEST_TIMEOUT_SECONDS = float(os.getenv("CITESHIELD_SMOKE_REQUEST_TIMEOUT_SECONDS", "30"))
READY_TIMEOUT_SECONDS = float(os.getenv("CITESHIELD_SMOKE_READY_TIMEOUT_SECONDS", "90"))


def wait_for_ready(client: httpx.Client) -> httpx.Response:
    deadline = monotonic() + READY_TIMEOUT_SECONDS
    last_error: str | None = None

    while monotonic() < deadline:
        try:
            response = client.get(f"{BASE_URL}/health")
            if response.status_code == 200:
                return response
            last_error = f"HTTP {response.status_code}: {response.text}"
        except httpx.HTTPError as exc:
            last_error = repr(exc)
        sleep(1)

    raise RuntimeError(f"API did not become ready at {BASE_URL}/health: {last_error}")


def request_with_retry(client: httpx.Client, method: str, path: str, **kwargs) -> httpx.Response:
    deadline = monotonic() + READY_TIMEOUT_SECONDS
    last_error: str | None = None

    while monotonic() < deadline:
        try:
            response = client.request(method, f"{BASE_URL}{path}", **kwargs)
            if response.status_code < 500:
                return response
            last_error = f"HTTP {response.status_code}: {response.text}"
        except httpx.HTTPError as exc:
            last_error = repr(exc)
        sleep(1)

    raise RuntimeError(f"{method} {path} did not complete successfully: {last_error}")


def main() -> int:
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        try:
            health = wait_for_ready(client)
            metrics = request_with_retry(client, "GET", "/metrics")
            ingest = request_with_retry(
                client,
                "POST",
                "/ingest",
                headers={"X-API-Key": TENANT_KEY},
                json={"source": "smoke.md", "text": "Employees must use VPN for internal dashboards."},
            )
            query = request_with_retry(
                client,
                "POST",
                "/query",
                headers={"X-API-Key": TENANT_KEY},
                json={"question": "What is the VPN rule?", "top_k": 3},
            )
        except RuntimeError as exc:
            print(f"Smoke test failed: {exc}", file=sys.stderr)
            return 1

    checks = [health.status_code == 200, metrics.status_code == 200, ingest.status_code == 200, query.status_code == 200]
    if all(checks):
        print("Smoke test passed")
        return 0

    print(
        "Smoke test failed:",
        {
            "base_url": BASE_URL,
            "health": health.status_code,
            "metrics": metrics.status_code,
            "ingest": ingest.status_code,
            "query": query.status_code,
        },
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
