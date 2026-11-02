"""Reading Tailscale's state and mapping this PC's HTTPS address to the gateway (ADR-025).

Every command line is fixed here; nothing the operator types reaches it.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.errors import DomainError

logger = logging.getLogger(__name__)

_WINDOWS_DEFAULT = Path("C:/Program Files/Tailscale/tailscale.exe")
_TIMEOUT_SECONDS = 15
# Tailscale prints a link when HTTPS certificates must first be switched on for the tailnet.
_ADMIN_LINK = re.compile(r"https://login\.tailscale\.com/[^\s\"']+")
INSTALL_URL = "https://tailscale.com/download/windows"


@dataclass(frozen=True)
class TailscaleState:
    installed: bool
    running: bool
    dns_name: str
    serving: bool


def _executable() -> str | None:
    found = shutil.which("tailscale")
    if found:
        return found
    return str(_WINDOWS_DEFAULT) if _WINDOWS_DEFAULT.is_file() else None


def _run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    executable = _executable()
    if executable is None:
        raise DomainError(
            "TAILSCALE_NOT_INSTALLED",
            "Tailscale isn't installed on this PC.",
            status_code=409,
            details={"install_url": INSTALL_URL},
        )
    return subprocess.run(  # noqa: S603 -- fixed argument lists only
        [executable, *arguments],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


class TailscaleClient:
    def state(self, gateway_port: int) -> TailscaleState:
        if _executable() is None:
            return TailscaleState(installed=False, running=False, dns_name="", serving=False)
        try:
            status = _run(["status", "--json"])
            data = json.loads(status.stdout or "{}")
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            return TailscaleState(installed=True, running=False, dns_name="", serving=False)
        running = data.get("BackendState") == "Running"
        dns_name = str((data.get("Self") or {}).get("DNSName") or "").rstrip(".").lower()
        return TailscaleState(
            installed=True,
            running=running,
            dns_name=dns_name,
            serving=running and self._serving(gateway_port),
        )

    def _serving(self, gateway_port: int) -> bool:
        try:
            result = _run(["serve", "status", "--json"])
        except (subprocess.TimeoutExpired, OSError):
            return False
        return f"127.0.0.1:{gateway_port}" in (result.stdout or "")

    def serve(self, gateway_port: int) -> None:
        """Forward https://<this PC>.ts.net to the gateway, in the background."""
        result = _run(["serve", "--bg", "--https=443", f"http://127.0.0.1:{gateway_port}"])
        if result.returncode != 0:
            output = f"{result.stdout}\n{result.stderr}"
            link = _ADMIN_LINK.search(output)
            logger.warning(
                "Tailscale serve did not start",
                extra={"event": "mobile_tailscale_serve_failed", "exit_code": result.returncode},
            )
            raise DomainError(
                "TAILSCALE_SERVE_FAILED",
                (
                    "Tailscale needs HTTPS switched on for your account first. Open the link, "
                    "allow it, then try again."
                    if link
                    else "Tailscale couldn't set up the phone address. Check that Tailscale is "
                    "signed in, then try again."
                ),
                status_code=409,
                details={"admin_url": link.group(0)} if link else {},
            )
        logger.info(
            "Tailscale now forwards the phone address",
            extra={"event": "mobile_tailscale_serving", "port": gateway_port},
        )

    def stop_serving(self) -> None:
        result = _run(["serve", "--https=443", "off"])
        if result.returncode != 0:
            raise DomainError(
                "TAILSCALE_SERVE_FAILED",
                "Tailscale couldn't remove the phone address. Try again.",
                status_code=409,
            )
        logger.info(
            "Tailscale stopped forwarding the phone address",
            extra={"event": "mobile_tailscale_stopped"},
        )
