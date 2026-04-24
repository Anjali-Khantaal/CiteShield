import sys
import httpx

BASE_URL = "http://127.0.0.1:8000"
TENANT_KEY = "tenant-a-dev-key"


def main() -> int:
    with httpx.Client(timeout=15.0) as client:
        health = client.get(f"{BASE_URL}/health")
        metrics = client.get(f"{BASE_URL}/metrics")
        ingest = client.post(
            f"{BASE_URL}/ingest",
            headers={"X-API-Key": TENANT_KEY},
            json={"source": "smoke.md", "text": "Employees must use VPN for internal dashboards."},
        )
        query = client.post(
            f"{BASE_URL}/query",
            headers={"X-API-Key": TENANT_KEY},
            json={"question": "What is the VPN rule?", "top_k": 3},
        )

    checks = [health.status_code == 200, metrics.status_code == 200, ingest.status_code == 200, query.status_code == 200]
    if all(checks):
        print("Smoke test passed")
        return 0

    print(
        "Smoke test failed:",
        {
            "health": health.status_code,
            "metrics": metrics.status_code,
            "ingest": ingest.status_code,
            "query": query.status_code,
        },
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
