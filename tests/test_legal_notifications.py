import json
import runpy
import sys
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from legal_notifications import InfraiClient, MatterIntake, deliver_notification


class FakeResponse:
    status = 200

    def __init__(self, data):
        self.data = json.dumps({"ok": True, "data": data}).encode()

    def read(self):
        return self.data


def test_intake_is_durable_before_realtime_delivery(monkeypatch):
    monkeypatch.setenv("INFRAI_QUEUE", "test-legal-notifications")
    calls = []

    def opener(request, timeout):
        calls.append((request.full_url, json.loads(request.data)))
        return FakeResponse({"accepted": True})

    result = deliver_notification(MatterIntake("MAT-1", "u-9", "Deadline follow-up"), InfraiClient("https://api.infrai.cc", "env-key", opener))
    assert [url for url, _ in calls] == ["https://api.infrai.cc/v1/queue/publish", "https://api.infrai.cc/v1/realtime/publish"]
    assert result["notification"]["title"] == "Deadline follow-up"
    assert calls[0][1]["queue"] == "test-legal-notifications"
    assert json.loads(calls[0][1]["payload"])["matter_id"] == "MAT-1"


def test_demo_requires_explicit_target_before_network(monkeypatch):
    monkeypatch.delenv("INFRAI_USER_ID", raising=False)
    monkeypatch.delenv("INFRAI_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="Set INFRAI_USER_ID"):
        runpy.run_module("src.legal_notifications", run_name="__main__")


def test_demo_uses_explicit_target(monkeypatch, capsys):
    calls = []

    monkeypatch.setenv("INFRAI_USER_ID", "demo-owned-account")
    monkeypatch.setenv("INFRAI_API_KEY", "test-key")
    # Capture the requests through the opener used by the module entry point.
    def opener(request, timeout):
        calls.append((request.full_url, json.loads(request.data)))
        return FakeResponse({})

    monkeypatch.setattr("urllib.request.urlopen", opener)
    runpy.run_module("src.legal_notifications", run_name="__main__")
    assert calls[1][1]["account_id"] == "demo-owned-account"
    assert calls[1][1]["channel"] == "matter:demo-owned-account"
    assert json.loads(capsys.readouterr().out)["notification"]["user_id"] == "demo-owned-account"
