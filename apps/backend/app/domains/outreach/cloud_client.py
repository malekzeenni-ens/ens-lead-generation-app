from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.core.errors import DomainError
from app.domains.outreach.cloud_prompt import CLOUD_POLISH_SYSTEM_PROMPT
from app.domains.outreach.schemas import OutreachDraftRefineResult
from app.domains.system.schemas import CLOUD_POLISH_EFFORT_MODELS

if TYPE_CHECKING:
    from anthropic.types import OutputConfigParam

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CloudPolishResult:
    value: OutreachDraftRefineResult
    input_tokens: int
    output_tokens: int
    request_id: str


def polish_with_anthropic(*, api_key: str, model: str, user_message: str) -> CloudPolishResult:
    # Imported here, not at module level: the SDK takes seconds to import, the feature is off by
    # default, and the desktop host gives the backend a fixed window to start listening.
    import anthropic

    client = anthropic.Anthropic(api_key=api_key, timeout=30.0, max_retries=2)
    output_config: OutputConfigParam = {
        "format": {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {"subject": {"type": "string"}, "body": {"type": "string"}},
                "required": ["subject", "body"],
                "additionalProperties": False,
            },
        }
    }
    if model in CLOUD_POLISH_EFFORT_MODELS:
        # Polishing one email needs little reasoning. These models think by default, and
        # thinking shares max_tokens with the answer, so low effort also prevents truncation.
        output_config["effort"] = "low"
    try:
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            system=CLOUD_POLISH_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            output_config=output_config,
        )
    except anthropic.AuthenticationError as exc:
        raise DomainError(
            "CLOUD_POLISH_AUTHENTICATION",
            "The saved API key was rejected. Save a new one in Settings.",
            status_code=409,
        ) from exc
    except anthropic.PermissionDeniedError as exc:
        raise DomainError(
            "CLOUD_POLISH_PERMISSION",
            "That API key is not permitted to use this model.",
            status_code=409,
        ) from exc
    except anthropic.NotFoundError as exc:
        raise DomainError(
            "CLOUD_POLISH_MODEL_UNAVAILABLE",
            "The selected cloud model is no longer available. Choose another model in Settings.",
            status_code=409,
        ) from exc
    except anthropic.RateLimitError as exc:
        retry_after = exc.response.headers.get("retry-after")
        message = "The cloud model is rate limited. Try again shortly."
        if retry_after:
            message = f"The cloud model is rate limited. Retry after {retry_after} seconds."
        raise DomainError("CLOUD_POLISH_RATE_LIMITED", message, status_code=503) from exc
    except anthropic.BadRequestError as exc:
        detail = str(exc).replace(api_key, "[redacted]")
        raise DomainError(
            "CLOUD_POLISH_BAD_REQUEST", f"The request was rejected: {detail}", status_code=502
        ) from exc
    except anthropic.APITimeoutError as exc:
        raise DomainError(
            "CLOUD_POLISH_TIMEOUT",
            "The cloud model took too long. The draft is unchanged.",
            status_code=504,
        ) from exc
    except anthropic.APIConnectionError as exc:
        raise DomainError(
            "CLOUD_POLISH_CONNECTION",
            "No internet connection, so the cloud model is unreachable.",
            status_code=503,
        ) from exc
    except anthropic.APIStatusError as exc:
        if exc.status_code >= 500:
            raise DomainError(
                "CLOUD_POLISH_UNAVAILABLE",
                "The cloud model is unavailable. Try again shortly.",
                status_code=503,
            ) from exc
        raise DomainError(
            "CLOUD_POLISH_PROVIDER_ERROR", "The cloud model rejected the request.", status_code=502
        ) from exc

    if response.stop_reason == "refusal":
        details: Any = getattr(response, "stop_details", None)
        category = (
            details.get("category", "unspecified")
            if isinstance(details, dict)
            else getattr(details, "category", None) or "unspecified"
        )
        raise DomainError(
            "CLOUD_POLISH_REFUSED",
            f"The cloud model declined this polish ({category}). The draft is unchanged.",
            status_code=502,
        )
    if response.stop_reason == "max_tokens":
        raise DomainError(
            "CLOUD_POLISH_TRUNCATED",
            "The cloud response was incomplete. The draft is unchanged.",
            status_code=502,
        )
    block = next((item for item in response.content if item.type == "text"), None)
    if block is None:
        raise DomainError(
            "CLOUD_POLISH_INVALID_RESPONSE",
            "The cloud model returned no text. The draft is unchanged.",
            status_code=502,
        )
    try:
        result = OutreachDraftRefineResult.model_validate_json(block.text)
    except Exception as exc:
        raise DomainError(
            "CLOUD_POLISH_INVALID_RESPONSE",
            "The cloud model returned an invalid response. The draft is unchanged.",
            status_code=502,
        ) from exc
    logger.info(
        "Cloud polish completed model=%s input_tokens=%s output_tokens=%s request_id=%s",
        model,
        response.usage.input_tokens,
        response.usage.output_tokens,
        response._request_id,
    )
    return CloudPolishResult(
        result,
        response.usage.input_tokens,
        response.usage.output_tokens,
        response._request_id or "",
    )
