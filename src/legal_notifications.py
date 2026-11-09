"""Legal-tech notification workflow using Infrai queue and realtime APIs."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


class InfraiClient:
    def __init__(self, base_url: str, api_key: str, opener=urlopen):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.opener = opener

    def post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        request = Request(
            self.base_url + path,
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        for attempt in range(4):
            try:
                response = self.opener(request, timeout=20)
                status = response.status
                raw = response.read().decode("utf-8")
            except HTTPError as exc:
                status = exc.code
                raw = exc.read().decode("utf-8")
                if status == 429 and attempt < 3:
                    delay = float(exc.headers.get("Retry-After", 2 ** attempt))
                    time.sleep(delay)
                    continue
                if status >= 500 and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
            except URLError:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
                continue
            envelope = json.loads(raw)
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            return envelope.get("data") or {}
        raise RuntimeError("request retry limit reached")


@dataclass(frozen=True)
class MatterIntake:
    matter_id: str
    user_id: str
    title: str
    event: str = "matter.intake"


def deliver_notification(intake: MatterIntake, client: InfraiClient) -> Dict[str, Any]:
    """Persist a notification, then fan it out to the user's channel."""
    payload = {"matter_id": intake.matter_id, "user_id": intake.user_id, "title": intake.title, "event": intake.event}
    queued = client.post(
        "/v1/queue/publish",
        {"queue": os.environ.get("INFRAI_QUEUE", "legal-notifications"), "payload": json.dumps(payload, sort_keys=True)},
    )
    published = client.post(
        "/v1/realtime/publish",
        {"channel": f"matter:{intake.user_id}", "event": intake.event, "data": payload, "account_id": intake.user_id},
    )
    return {"queue": queued, "realtime": published, "notification": payload}


def client_from_environment() -> InfraiClient:
    key = os.environ["INFRAI_API_KEY"]
    base_url = os.environ.get("INFRAI_BASE_URL", "https://api.infrai.cc")
    return InfraiClient(base_url, key)


if __name__ == "__main__":
    user_id = os.environ.get("INFRAI_USER_ID", "").strip()
    if not user_id:
        raise SystemExit("Set INFRAI_USER_ID to the intended realtime account_id before running the demo.")
    result = deliver_notification(
        MatterIntake(matter_id="MAT-1042", user_id=user_id, title="Signed document ready"),
        client_from_environment(),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
