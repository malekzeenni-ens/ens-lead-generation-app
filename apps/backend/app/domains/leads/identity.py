from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_SOCIAL_HOSTS = {
    "instagram": {"instagram.com", "www.instagram.com"},
    "facebook": {"facebook.com", "www.facebook.com", "m.facebook.com", "fb.com", "www.fb.com"},
}


def valid_public_email(value: str | None) -> bool:
    return bool(value and len(value) <= 320 and _EMAIL_PATTERN.fullmatch(value))


def phone_match_key(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(character for character in value if character.isdigit())
    return digits[-10:] if len(digits) >= 10 else (digits or None)


def social_identity(value: str, platform: str | None = None) -> tuple[str, str, str]:
    parsed = urlparse(value.strip())
    host = (parsed.hostname or "").casefold()
    selected = platform
    if selected is None:
        selected = next((name for name, hosts in _SOCIAL_HOSTS.items() if host in hosts), "other")
    if selected in _SOCIAL_HOSTS and host not in _SOCIAL_HOSTS[selected]:
        raise ValueError(f"The profile URL is not a {selected.title()} URL")

    if selected == "facebook" and parsed.path.casefold().rstrip("/") == "/profile.php":
        handle = (parse_qs(parsed.query).get("id") or [""])[0]
    else:
        handle = next((part for part in parsed.path.split("/") if part), "")
    handle = handle.removeprefix("@").casefold()
    blocked = {"", "accounts", "explore", "p", "reel", "reels", "stories", "share", "groups"}
    if selected in _SOCIAL_HOSTS and handle in blocked:
        raise ValueError("Provide a public business profile URL, not a post or platform page")

    if selected == "instagram":
        canonical = f"https://www.instagram.com/{handle}"
    elif selected == "facebook":
        canonical = f"https://www.facebook.com/{handle}"
    else:
        canonical = value.strip().split("#", 1)[0]
    return selected, handle[:200], canonical[:2048]
