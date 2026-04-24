from locust import HttpUser, between, task


class CiteShieldUser(HttpUser):
    wait_time = between(0.5, 2.0)
    headers = {"X-API-Key": "tenant-a-dev-key"}

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
