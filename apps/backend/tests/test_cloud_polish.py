from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.errors import DomainError
from app.db.models import AuditEvent
from app.domains.outreach import cloud_client
from tests.test_outreach_drafts import _batch, _ready_lead, _template


@pytest.mark.parametrize(
    ("error_type", "status_code"),
    [
        ("AuthenticationError", 409),
        ("PermissionDeniedError", 409),
        ("RateLimitError", 503),
        ("BadRequestError", 502),
        ("APITimeoutError", 504),
        ("APIConnectionError", 503),
        ("APIStatusError", 503),
    ],
)
def test_anthropic_errors_map_to_operator_status(
    monkeypatch: Any, error_type: str, status_code: int
) -> None:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(
        {
            "AuthenticationError": 401,
            "PermissionDeniedError": 403,
            "RateLimitError": 429,
            "BadRequestError": 400,
        }.get(error_type, 503),
        request=request,
        headers={"retry-after": "7"},
    )
    error_class = getattr(cloud_client.anthropic, error_type)
    if error_type in {"APITimeoutError", "APIConnectionError"}:
        error = error_class(request=request)
    else:
        error = error_class("provider failure", response=response, body={})

    class FakeMessages:
        @staticmethod
        def create(**_: Any) -> Any:
            raise error

    class FakeAnthropic:
        messages = FakeMessages()

        def __init__(self, **_: Any) -> None:
            pass

    monkeypatch.setattr(cloud_client.anthropic, "Anthropic", FakeAnthropic)
    with pytest.raises(DomainError) as caught:
        cloud_client.polish_with_anthropic(
            api_key="sk-ant-test-secret", model="claude-sonnet-5", user_message="{}"
        )
    assert caught.value.status_code == status_code


def test_refusal_is_reported_without_reading_response_content(monkeypatch: Any) -> None:
    class FakeMessages:
        @staticmethod
        def create(**_: Any) -> Any:
            return type(
                "Refusal",
                (),
                {
                    "stop_reason": "refusal",
                    "stop_details": type("Details", (), {"category": "general_harms"})(),
                    "content": [],
                },
            )()

    class FakeAnthropic:
        messages = FakeMessages()

        def __init__(self, **_: Any) -> None:
            pass

    monkeypatch.setattr(cloud_client.anthropic, "Anthropic", FakeAnthropic)
    with pytest.raises(DomainError, match="general_harms"):
        cloud_client.polish_with_anthropic(
            api_key="sk-ant-test-secret", model="claude-sonnet-5", user_message="{}"
        )


def _enable(client: TestClient) -> None:
    response = client.patch("/api/v1/system/settings", json={"cloud_polish_enabled": True})
    assert response.status_code == 200


def _save_key(client: TestClient) -> None:
    response = client.put("/api/v1/system/cloud-polish", json={"api_key": "sk-ant-test-secret"})
    assert response.status_code == 200


def test_disabled_by_default_and_missing_key_are_explicit(client: TestClient) -> None:
    assert client.get("/api/v1/system/settings").json()["cloud_polish_enabled"] is False
    assert client.get("/api/v1/system/cloud-polish").json() == {
        "configured": False,
        "enabled": False,
        "model": "claude-sonnet-5",
    }
    disabled = client.post(
        "/api/v1/outreach/drafts/unknown/polish", json={"subject": "S", "body": "B"}
    )
    assert disabled.status_code == 409
    assert disabled.json()["code"] == "CLOUD_POLISH_DISABLED"
    _enable(client)
    missing = client.post(
        "/api/v1/outreach/drafts/unknown/polish", json={"subject": "S", "body": "B"}
    )
    assert missing.status_code == 409
    assert missing.json()["code"] == "CLOUD_POLISH_NOT_CONFIGURED"


def test_polish_sends_only_one_lead_context_and_does_not_mutate_draft(
    client: TestClient,
    app: Any,
    campaign_payload: dict[str, object],
    monkeypatch: Any,
    caplog: Any,
) -> None:
    campaign, lead = _ready_lead(client, campaign_payload)
    other_payload = {
        "campaign_id": campaign["id"],
        "business_name": "Unrelated Workspace Prospect",
        "segment": "Bakeries and home bakers",
        "location": "Dunstable",
        "website": "https://other.example.test",
        "contact_classification": "unknown",
        "source": {
            "name": "Manual entry",
            "source_type": "manual",
            "source_url": "https://other.example.test",
            "classification": "user_verified",
        },
    }
    assert client.post("/api/v1/leads", json=other_payload).status_code == 201
    draft = _batch(client, campaign, lead, _template(client))["drafts"][0]
    _enable(client)
    _save_key(client)
    captured: dict[str, Any] = {}

    def fake_polish(
        *, api_key: str, model: str, user_message: str
    ) -> cloud_client.CloudPolishResult:
        captured.update(api_key=api_key, model=model, user_message=user_message)
        return cloud_client.CloudPolishResult(
            value=cloud_client.OutreachDraftRefineResult(subject="Polished", body="A better note."),
            input_tokens=500,
            output_tokens=80,
            request_id="req-test",
        )

    monkeypatch.setattr("app.domains.outreach.service.polish_with_anthropic", fake_polish)
    response = client.post(
        f"/api/v1/outreach/drafts/{draft['id']}/polish",
        json={
            "subject": draft["current_revision"]["subject"],
            "body": draft["current_revision"]["body"],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"subject": "Polished", "body": "A better note."}
    assert captured["api_key"] == "sk-ant-test-secret"
    assert "Example Celebration Cakes" in captured["user_message"]
    assert "workspace_snapshot" not in captured["user_message"]
    assert "£" not in captured["user_message"]
    unchanged = client.get(f"/api/v1/outreach/batches/{draft['batch_id']}").json()["drafts"][0]
    assert unchanged["current_revision"] == draft["current_revision"]
    assert unchanged["revision_count"] == 1
    status = client.get("/api/v1/system/cloud-polish").json()
    assert "sk-ant-test-secret" not in str(status)
    assert "sk-ant-test-secret" not in caplog.text
    assert "Luton Bakery Partnerships" not in captured["user_message"]
    assert "Unrelated Workspace Prospect" not in captured["user_message"]
    with app.state.database.session_factory() as session:
        event = session.query(AuditEvent).filter_by(action="outreach.draft_cloud_polished").one()
        assert "sk-ant-test-secret" not in str(event.summary)
        assert event.summary["request_id"] == "req-test"


def test_cloud_polish_model_is_allowlisted(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/system/settings", json={"cloud_polish_model": "arbitrary-model"}
    )
    assert response.status_code == 422


def test_prices_are_stripped_from_cloud_response(
    client: TestClient, campaign_payload: dict[str, object], monkeypatch: Any
) -> None:
    campaign, lead = _ready_lead(client, campaign_payload)
    draft = _batch(client, campaign, lead, _template(client))["drafts"][0]
    _enable(client)
    _save_key(client)

    def fake_polish(
        *, api_key: str, model: str, user_message: str
    ) -> cloud_client.CloudPolishResult:
        return cloud_client.CloudPolishResult(
            value=cloud_client.OutreachDraftRefineResult(
                subject="A sign for £25", body="This costs £25."
            ),
            input_tokens=20,
            output_tokens=10,
            request_id="req-price",
        )

    monkeypatch.setattr("app.domains.outreach.service.polish_with_anthropic", fake_polish)
    result = client.post(
        f"/api/v1/outreach/drafts/{draft['id']}/polish",
        json={"subject": "Original", "body": "Original body"},
    )
    assert result.status_code == 200
    assert "\N{POUND SIGN}" not in result.text


def test_response_price_that_survives_stripping_is_rejected(
    client: TestClient, campaign_payload: dict[str, object], monkeypatch: Any
) -> None:
    campaign, lead = _ready_lead(client, campaign_payload)
    draft = _batch(client, campaign, lead, _template(client))["drafts"][0]
    _enable(client)
    _save_key(client)
    monkeypatch.setattr("app.domains.outreach.service.strip_prices", lambda value: value)
    monkeypatch.setattr(
        "app.domains.outreach.service.polish_with_anthropic",
        lambda **_: cloud_client.CloudPolishResult(
            value=cloud_client.OutreachDraftRefineResult(
                subject="A sign for £25", body="Discuss this £25 offer."
            ),
            input_tokens=20,
            output_tokens=10,
            request_id="req-price-survived",
        ),
    )
    response = client.post(
        f"/api/v1/outreach/drafts/{draft['id']}/polish",
        json={"subject": "Original", "body": "Original body"},
    )
    assert response.status_code == 502
    assert response.json()["code"] == "CLOUD_POLISH_PRICE_BLOCKED"
