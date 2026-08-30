from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, TypeVar, cast

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.core.errors import DomainError
from app.domains.campaign_assistant.schemas import (
    CampaignDraftProposal,
    OllamaGenerationMetrics,
    ResourceProfile,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass(frozen=True)
class OllamaResult:
    proposal: CampaignDraftProposal
    metrics: OllamaGenerationMetrics


@dataclass(frozen=True)
class OllamaChatResult:
    content: str
    artifact_filename: str | None
    artifact_content: str | None
    metrics: OllamaGenerationMetrics


@dataclass(frozen=True)
class OllamaStructuredResult[ModelT: BaseModel]:
    value: ModelT
    metrics: OllamaGenerationMetrics


# Keep this schema deliberately inline and limited to the JSON-Schema features
# supported by Ollama's llama.cpp grammar converter. Pydantic's full generated
# schema includes validation metadata and open-ended values which are validated
# after inference but cannot be compiled by every supported Ollama build.
_OLLAMA_CAMPAIGN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "description": {
            "anyOf": [
                {"type": "string"},
                {"type": "null"},
            ]
        },
        "segment": {"type": "string", "minLength": 1},
        "primary_location": {
            "type": "string",
            "minLength": 1,
        },
        "radius_miles": {"type": "number"},
        "keywords": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
            "maxItems": 3,
        },
        "exclusion_keywords": {
            "type": "array",
            "items": {"type": "string"},
        },
        "product_categories": {
            "type": "array",
            "items": {"type": "string"},
        },
        "product_family_id": {
            "anyOf": [
                {"type": "string", "minLength": 36},
                {"type": "null"},
            ]
        },
        "discovery_sources": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "string",
                "enum": [
                    "manual",
                    "google_places",
                    "instagram",
                    "public_registries",
                ],
            },
        },
        "weekly_shortlist_size": {"type": "integer"},
        "minimum_score_threshold": {"type": "integer"},
        "preferred_channels": {
            "type": "array",
            "items": {"type": "string", "enum": ["email", "instagram"]},
        },
        "offer_settings": {
            "type": "object",
            "properties": {
                "digital_mock_up": {"type": "boolean"},
                "introductory_pricing": {"type": "boolean"},
            },
            "required": ["digital_mock_up", "introductory_pricing"],
        },
        "discovery_mode": {
            "type": "string",
            "enum": ["manual", "combined"],
        },
        "weekly_outreach_enabled": {"type": "boolean"},
        "weekly_outreach_template_id": {"type": "null"},
        "weekly_outreach_provider": {
            "type": "string",
            "enum": ["scoring"],
        },
        "status": {"type": "string", "enum": ["paused"]},
    },
    "required": [
        "name",
        "description",
        "segment",
        "primary_location",
        "radius_miles",
        "keywords",
        "exclusion_keywords",
        "product_categories",
        "product_family_id",
        "discovery_sources",
        "weekly_shortlist_size",
        "minimum_score_threshold",
        "preferred_channels",
        "offer_settings",
        "discovery_mode",
        "weekly_outreach_enabled",
        "weekly_outreach_template_id",
        "weekly_outreach_provider",
        "status",
    ],
}

_OLLAMA_OVERRIDE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "minLength": 1},
        "items": {
            "type": "array",
            "minItems": 1,
            "maxItems": 7,
            "items": {
                "type": "object",
                "properties": {
                    "rule_id": {
                        "type": "string",
                        "enum": [
                            "focused-audience",
                            "local-radius",
                            "focused-keywords",
                            "relevance-exclusions",
                            "conservative-shortlist",
                            "catalogue-relevance",
                            "billable-provider",
                        ],
                    },
                    "field": {"type": "string", "minLength": 1},
                    "playbook_recommendation": {"type": "string"},
                    "requested_value": {"type": "string"},
                    "impact": {"type": "string", "minLength": 1},
                },
                "required": [
                    "rule_id",
                    "field",
                    "playbook_recommendation",
                    "requested_value",
                    "impact",
                ],
            },
        },
    },
    "required": ["summary", "items"],
}


def _proposal_variant(
    outcome: str,
    *,
    campaign: dict[str, Any],
    override_request: dict[str, Any],
    questions: dict[str, Any],
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "outcome": {"type": "string", "const": outcome},
            "assistant_message": {"type": "string", "minLength": 1},
            "questions": questions,
            "assumptions": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "maxItems": 6,
            },
            "warnings": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "maxItems": 20,
            },
            "campaign": campaign,
            "override_request": override_request,
        },
        "required": [
            "outcome",
            "assistant_message",
            "questions",
            "assumptions",
            "warnings",
            "campaign",
            "override_request",
        ],
    }


_NO_QUESTIONS_SCHEMA = {"type": "array", "items": {"type": "string"}, "maxItems": 0}
_NULL_SCHEMA = {"type": "null"}
OLLAMA_CAMPAIGN_PROPOSAL_SCHEMA: dict[str, Any] = {
    "oneOf": [
        _proposal_variant(
            "draft_ready",
            campaign=_OLLAMA_CAMPAIGN_SCHEMA,
            override_request=_NULL_SCHEMA,
            questions=_NO_QUESTIONS_SCHEMA,
        ),
        _proposal_variant(
            "clarification_required",
            campaign=_NULL_SCHEMA,
            override_request=_NULL_SCHEMA,
            questions={
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "minItems": 1,
                "maxItems": 3,
            },
        ),
        _proposal_variant(
            "confirmation_required",
            campaign=_NULL_SCHEMA,
            override_request=_OLLAMA_OVERRIDE_SCHEMA,
            questions=_NO_QUESTIONS_SCHEMA,
        ),
        _proposal_variant(
            "override_not_allowed",
            campaign=_NULL_SCHEMA,
            override_request=_NULL_SCHEMA,
            questions=_NO_QUESTIONS_SCHEMA,
        ),
    ]
}


class OllamaClient:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self._owns_client = client is None
        self._client = client or self._create_client()

    def _create_client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.settings.ollama_base_url,
            timeout=httpx.Timeout(self.settings.ollama_timeout_seconds, connect=2.0),
        )

    def open(self) -> None:
        if self._client.is_closed and self._owns_client:
            self._client = self._create_client()

    def close(self) -> None:
        self._client.close()

    def status(self) -> tuple[bool, set[str], set[str]]:
        try:
            tags_response = self._client.get("/api/tags")
            tags_response.raise_for_status()
            ps_response = self._client.get("/api/ps")
            ps_response.raise_for_status()
        except (httpx.HTTPError, ValueError):
            return False, set(), set()
        installed = {
            str(item.get("name") or item.get("model"))
            for item in tags_response.json().get("models", [])
            if item.get("name") or item.get("model")
        }
        loaded = {
            str(item.get("name") or item.get("model"))
            for item in ps_response.json().get("models", [])
            if item.get("name") or item.get("model")
        }
        return True, installed, loaded

    def generate(
        self,
        messages: list[dict[str, str]],
        profile: ResourceProfile,
    ) -> OllamaResult:
        schema = deepcopy(OLLAMA_CAMPAIGN_PROPOSAL_SCHEMA)
        campaign_schema = schema["oneOf"][0]["properties"]["campaign"]
        campaign_schema["properties"]["keywords"]["maxItems"] = (
            self.settings.discovery_max_queries
        )
        result = self.generate_structured(
            messages,
            profile,
            schema=schema,
            model_cls=CampaignDraftProposal,
            error_prefix="CAMPAIGN_ASSISTANT",
        )
        return OllamaResult(proposal=result.value, metrics=result.metrics)

    def generate_structured(
        self,
        messages: list[dict[str, str]],
        profile: ResourceProfile,
        *,
        schema: dict[str, Any],
        model_cls: type[ModelT],
        error_prefix: str,
    ) -> OllamaStructuredResult[ModelT]:
        protected = profile == ResourceProfile.DESIGN_SOFTWARE
        options = {
            "num_ctx": (
                self.settings.ollama_protected_context
                if protected
                else self.settings.ollama_standard_context
            ),
            "num_predict": (
                self.settings.ollama_protected_output_limit
                if protected
                else self.settings.ollama_standard_output_limit
            ),
            "temperature": 0,
        }
        payload: dict[str, Any] = {
            "model": self.settings.ollama_model,
            "messages": messages,
            "stream": False,
            "keep_alive": 0 if protected else self.settings.ollama_standard_keep_alive,
            "format": schema,
            "options": options,
        }
        try:
            body = self._post_chat(payload, error_prefix=error_prefix)
            content = body["message"]["content"]
            value = model_cls.model_validate_json(content)
        except (ValueError, json.JSONDecodeError, ValidationError) as exc:
            message = "The local model returned a response that could not be validated."
            if error_prefix == "CAMPAIGN_ASSISTANT":
                message = "The local model returned a draft that could not be validated."
            raise DomainError(
                f"{error_prefix}_INVALID_RESPONSE",
                message,
                details={"validation": str(exc)[:2_000]},
            ) from exc
        return OllamaStructuredResult(
            value=value,
            metrics=OllamaGenerationMetrics(
                model=str(body.get("model") or self.settings.ollama_model),
                model_digest=body.get("model_digest"),
                total_duration_ms=(
                    int(body["total_duration"] / 1_000_000)
                    if isinstance(body.get("total_duration"), int)
                    else None
                ),
                prompt_eval_count=body.get("prompt_eval_count"),
                eval_count=body.get("eval_count"),
            ),
        )

    def _post_chat(self, payload: dict[str, Any], *, error_prefix: str) -> dict[str, Any]:
        try:
            response = self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            body = cast(dict[str, Any], response.json())
            content = body.get("message", {}).get("content")
            if not isinstance(content, str) or len(content.encode("utf-8")) > 100_000:
                raise ValueError("Ollama returned an empty or oversized response")
            return body
        except httpx.TimeoutException as exc:
            message = "The local assistant took too long to answer."
            if error_prefix == "CAMPAIGN_ASSISTANT":
                message = "The local model took too long to prepare the campaign draft."
            raise DomainError(
                f"{error_prefix}_TIMEOUT",
                message,
                status_code=504,
            ) from exc
        except httpx.ConnectError as exc:
            raise DomainError(
                "OLLAMA_UNAVAILABLE",
                "Ollama is not installed or is not currently running.",
                status_code=503,
            ) from exc
        except httpx.HTTPStatusError as exc:
            message = "Ollama could not answer that request."
            if error_prefix == "CAMPAIGN_ASSISTANT":
                message = "Ollama could not prepare the campaign draft."
            if exc.response.status_code == 404:
                message = f"The local model {self.settings.ollama_model} is not installed."
            raise DomainError("OLLAMA_REQUEST_FAILED", message, status_code=503) from exc

    def chat(
        self,
        messages: list[dict[str, str]],
        profile: ResourceProfile,
        *,
        artifact_format: str | None = None,
    ) -> OllamaChatResult:
        protected = profile == ResourceProfile.DESIGN_SOFTWARE
        payload: dict[str, Any] = {
            "model": self.settings.ollama_model,
            "messages": messages,
            "stream": False,
            "keep_alive": 0 if protected else self.settings.ollama_standard_keep_alive,
            "options": {
                "num_ctx": (
                    self.settings.ollama_protected_context
                    if protected
                    else self.settings.ollama_standard_context
                ),
                "num_predict": (
                    self.settings.ollama_protected_output_limit
                    if protected
                    else self.settings.ollama_standard_output_limit
                ),
                "temperature": 0.2,
            },
        }
        if artifact_format is not None:
            payload["format"] = {
                "type": "object",
                "properties": {
                    "assistant_message": {"type": "string", "minLength": 1},
                    "artifact_filename": {"type": "string", "minLength": 1},
                    "artifact_content": {"type": "string", "minLength": 1},
                },
                "required": [
                    "assistant_message",
                    "artifact_filename",
                    "artifact_content",
                ],
            }
        try:
            response = self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            body = response.json()
            raw_content = body.get("message", {}).get("content")
            if not isinstance(raw_content, str) or len(raw_content.encode("utf-8")) > 200_000:
                raise ValueError("Ollama returned an empty or oversized response")
            artifact_filename: str | None = None
            artifact_content: str | None = None
            content = raw_content.strip()
            if artifact_format is not None:
                structured = json.loads(raw_content)
                content = structured.get("assistant_message")
                artifact_filename = structured.get("artifact_filename")
                artifact_content = structured.get("artifact_content")
                if not all(
                    isinstance(value, str) and value.strip()
                    for value in (content, artifact_filename, artifact_content)
                ):
                    raise ValueError("Ollama returned an incomplete attachment response")
        except httpx.TimeoutException as exc:
            raise DomainError(
                "ASSISTANT_TIMEOUT",
                "The local assistant took too long to answer.",
                status_code=504,
            ) from exc
        except httpx.ConnectError as exc:
            raise DomainError(
                "OLLAMA_UNAVAILABLE",
                "Ollama is not installed or is not currently running.",
                status_code=503,
            ) from exc
        except httpx.HTTPStatusError as exc:
            message = "Ollama could not answer that request."
            if exc.response.status_code == 404:
                message = f"The local model {self.settings.ollama_model} is not installed."
            raise DomainError("OLLAMA_REQUEST_FAILED", message, status_code=503) from exc
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise DomainError(
                "ASSISTANT_INVALID_RESPONSE",
                "The local model returned an answer that could not be read.",
                details={"validation": str(exc)[:2_000]},
            ) from exc
        return OllamaChatResult(
            content=content,
            artifact_filename=artifact_filename,
            artifact_content=artifact_content,
            metrics=OllamaGenerationMetrics(
                model=str(body.get("model") or self.settings.ollama_model),
                model_digest=body.get("model_digest"),
                total_duration_ms=(
                    int(body["total_duration"] / 1_000_000)
                    if isinstance(body.get("total_duration"), int)
                    else None
                ),
                prompt_eval_count=body.get("prompt_eval_count"),
                eval_count=body.get("eval_count"),
            ),
        )

    def unload(self) -> None:
        try:
            self._client.post(
                "/api/generate",
                json={"model": self.settings.ollama_model, "keep_alive": 0},
                timeout=10.0,
            )
        except (httpx.HTTPError, RuntimeError):
            return
