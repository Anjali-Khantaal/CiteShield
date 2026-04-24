import os

from locust import HttpUser, between, task


class CiteShieldUser(HttpUser):
    host = os.getenv("CITESHIELD_BASE_URL", "http://127.0.0.1:8000")
    wait_time = between(0.5, 2.0)
    headers = {
        "X-API-Key": os.getenv(
            "CITESHIELD_TENANT_API_KEY",
            os.getenv("TENANT_A_API_KEY", "tenant-a-dev-key"),
        )
    }

    @task(3)
    def health(self):
        self.client.get("/health")

    @task(5)
    def query(self):
        self.client.post("/query", headers=self.headers, json={"question": "What is the VPN rule?", "top_k": 3})

    @task(1)
    def ingest(self):
        self.client.post(
            "/ingest",
            headers=self.headers,
            json={"source": "locust.md", "text": "Employees must use VPN for internal dashboards."},
        )
