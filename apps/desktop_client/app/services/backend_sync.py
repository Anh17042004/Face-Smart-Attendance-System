import requests


class BackendSyncClient:
    def __init__(self, base_url: str, timeout_seconds: int = 3):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = int(timeout_seconds)

    def _request_json(self, method: str, path: str, payload: dict | None = None):
        url = f"{self.base_url}{path}"
        try:
            resp = requests.request(method=method, url=url, json=payload, timeout=self.timeout_seconds)
            if resp.status_code < 300:
                return True, resp.json() if resp.text else {}
            return False, {"error": f"http_{resp.status_code}", "detail": resp.text}
        except Exception as exc:
            return False, {"error": str(exc)}

    def check_online(self):
        ok, _ = self._request_json("GET", "/health")
        return ok

    def send_event(self, payload: dict):
        ok, data = self._request_json("POST", "/api/v1/attendance/events", payload)
        if ok:
            return True, data
        return False, data.get("error", "unknown_error")

    def match_embeddings_batch(self, embeddings: list[list[float]], threshold: float, min_vote_count: int):
        payload = {
            "embeddings": embeddings,
            "threshold": float(threshold),
            "min_vote_count": int(min_vote_count),
        }
        return self._request_json("POST", "/api/v1/recognition/match-batch", payload)

    def enroll_embedding(
        self,
        employee_code: str,
        user_name: str,
        embedding: list[float],
        model_version: str = "arcface.onnx",
    ):
        payload = {
            "employee_code": employee_code,
            "user_name": user_name,
            "embedding": embedding,
            "model_version": model_version,
        }
        return self._request_json("POST", "/api/v1/recognition/enroll", payload)
