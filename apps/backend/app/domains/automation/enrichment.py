from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx

from app.core.config import Settings

USER_AGENT = "EtchNShineLeadResearch/0.1 (operator-initiated local research)"


class EnrichmentFailure(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message


@dataclass(frozen=True)
class WebsiteEvidence:
    final_url: str
    title: str | None
    description: str | None
    public_emails: list[str]
    public_phones: list[str]
    social_links: list[str]
    contact_links: list[str]
    same_host_links: list[str]
    pages_checked: list[str]


_EMAIL_PATTERN = re.compile(r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![\w.-])", re.I)
_UK_PHONE_PATTERN = re.compile(r"(?<!\d)(?:(?:\+44\s?\(?0?\)?|0)(?:[\s().-]*\d){9,10})(?!\d)")


class _EvidenceParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title_parts: list[str] = []
        self.description: str | None = None
        self.public_emails: set[str] = set()
        self.public_phones: set[str] = set()
        self.social_links: set[str] = set()
        self.contact_links: set[str] = set()
        self.same_host_links: set[str] = set()
        self._in_title = False
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.casefold(): value or "" for key, value in attrs}
        if tag.casefold() == "title":
            self._in_title = True
        if tag.casefold() in {"script", "style", "noscript"}:
            self._ignored_depth += 1
        if tag.casefold() == "meta" and values.get("name", "").casefold() == "description":
            content = values.get("content", "").strip()
            if content:
                self.description = content[:1_000]
        if tag.casefold() != "a":
            return
        href = values.get("href", "").strip()
        if href.casefold().startswith("mailto:"):
            email = href[7:].split("?", 1)[0].strip()
            if email and len(email) <= 320:
                self.public_emails.add(email)
        elif href.casefold().startswith("tel:"):
            phone = href[4:].split("?", 1)[0].strip()
            if phone and len(phone) <= 100:
                self.public_phones.add(phone)
        elif urlparse(urljoin(self.base_url, href)).hostname in {
            "instagram.com",
            "www.instagram.com",
            "facebook.com",
            "www.facebook.com",
            "m.facebook.com",
            "fb.com",
            "www.fb.com",
        }:
            absolute = urljoin(self.base_url, href).split("#", 1)[0]
            self.social_links.add(absolute[:2_048])
        elif href and any(term in href.casefold() for term in ("contact", "about")):
            absolute = urljoin(self.base_url, href)
            if urlparse(absolute).scheme in {"http", "https"}:
                self.contact_links.add(absolute[:2_048])
        elif href:
            absolute = urljoin(self.base_url, href).split("#", 1)[0]
            parsed = urlparse(absolute)
            base_host = (urlparse(self.base_url).hostname or "").casefold()
            if (
                parsed.scheme in {"http", "https"}
                and (parsed.hostname or "").casefold() == base_host
                and len(self.same_host_links) < 200
            ):
                self.same_host_links.add(absolute[:2_048])

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "title":
            self._in_title = False
        if tag.casefold() in {"script", "style", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
        for email in _EMAIL_PATTERN.findall(data):
            if len(email) <= 320:
                self.public_emails.add(email)
        for phone in _UK_PHONE_PATTERN.findall(data):
            cleaned = " ".join(phone.split()).strip(" .,-")
            if cleaned:
                self.public_phones.add(cleaned)


class SafeWebsiteEnricher:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.Client(
            timeout=settings.enrichment_timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html, text/plain;q=0.5"},
        )

    @staticmethod
    def _validate_and_pin_address(value: str) -> str:
        """Resolve and validate the URL's host, returning a single safe IP to connect to.

        The caller must connect directly to this returned IP instead of letting
        the HTTP client re-resolve the hostname. Validating here and resolving
        again at connect time would leave a DNS-rebinding window where a host
        that resolved publicly during this check could resolve to a private
        address by the time the request is actually sent.
        """
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise EnrichmentFailure(
                "WEBSITE_URL_UNSAFE", "The website URL is not eligible for enrichment."
            )
        try:
            port = parsed.port
        except ValueError as exc:
            raise EnrichmentFailure(
                "WEBSITE_URL_UNSAFE", "The website URL is not eligible for enrichment."
            ) from exc
        if parsed.username or parsed.password or port not in {None, 80, 443}:
            raise EnrichmentFailure(
                "WEBSITE_URL_UNSAFE", "The website URL is not eligible for enrichment."
            )
        try:
            addresses: set[str] = {
                str(item[4][0])
                for item in socket.getaddrinfo(
                    parsed.hostname, port or 443, type=socket.SOCK_STREAM
                )
            }
        except OSError as exc:
            raise EnrichmentFailure(
                "WEBSITE_DNS_FAILED", "The website address could not be resolved safely."
            ) from exc
        if not addresses:
            raise EnrichmentFailure("WEBSITE_DNS_FAILED", "The website address did not resolve.")
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                raise EnrichmentFailure(
                    "WEBSITE_ADDRESS_BLOCKED",
                    "The website resolves to a private or reserved network address.",
                )
        return sorted(addresses)[0]

    def _fetch(self, url: str, accepted_types: tuple[str, ...]) -> tuple[bytes, str]:
        current = url
        for _ in range(4):
            parsed = urlparse(current)
            pinned_ip = self._validate_and_pin_address(current)
            connect_port = parsed.port or (443 if parsed.scheme == "https" else 80)
            connect_host = f"[{pinned_ip}]" if ":" in pinned_ip else pinned_ip
            connect_url = urlunparse(parsed._replace(netloc=f"{connect_host}:{connect_port}"))
            try:
                with self.client.stream(
                    "GET",
                    connect_url,
                    headers={"Host": parsed.hostname or ""},
                    extensions={"sni_hostname": parsed.hostname or ""},
                ) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise EnrichmentFailure(
                                "WEBSITE_REDIRECT_INVALID",
                                "The website returned an invalid redirect.",
                            )
                        current = urljoin(current, location)
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").casefold()
                    if not any(value in content_type for value in accepted_types):
                        raise EnrichmentFailure(
                            "WEBSITE_CONTENT_UNSUPPORTED",
                            "The website did not return supported text content.",
                        )
                    declared = response.headers.get("content-length")
                    if declared and int(declared) > self.settings.enrichment_max_bytes:
                        raise EnrichmentFailure(
                            "WEBSITE_CONTENT_TOO_LARGE",
                            "The website response exceeded the safe limit.",
                        )
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > self.settings.enrichment_max_bytes:
                            raise EnrichmentFailure(
                                "WEBSITE_CONTENT_TOO_LARGE",
                                "The website response exceeded the safe limit.",
                            )
                    return bytes(content), current
            except EnrichmentFailure:
                raise
            except (httpx.HTTPError, ValueError) as exc:
                raise EnrichmentFailure(
                    "WEBSITE_FETCH_FAILED", "The public website could not be enriched safely."
                ) from exc
        raise EnrichmentFailure(
            "WEBSITE_REDIRECT_LIMIT", "The website exceeded the safe redirect limit."
        )

    def enrich(self, url: str) -> WebsiteEvidence:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        robots = RobotFileParser()
        robots_available = False
        try:
            content, _ = self._fetch(robots_url, ("text/plain", "text/"))
            robots.parse(content.decode("utf-8", errors="replace").splitlines())
            robots_available = True
            if not robots.can_fetch(USER_AGENT, url):
                raise EnrichmentFailure(
                    "WEBSITE_ROBOTS_DISALLOWED",
                    "The website's robots policy does not allow enrichment.",
                )
        except EnrichmentFailure as exc:
            if exc.code not in {"WEBSITE_FETCH_FAILED", "WEBSITE_CONTENT_UNSUPPORTED"}:
                raise
        html, final_url = self._fetch(url, ("text/html",))
        parsers: list[_EvidenceParser] = []

        def parse_page(content: bytes, page_url: str) -> _EvidenceParser:
            page_parser = _EvidenceParser(page_url)
            page_parser.feed(content.decode("utf-8", errors="replace"))
            parsers.append(page_parser)
            return page_parser

        home = parse_page(html, final_url)
        home_host = (urlparse(final_url).hostname or "").casefold().removeprefix("www.")
        pages_checked = [final_url]
        contact_pages = [
            link
            for link in sorted(home.contact_links)
            if (urlparse(link).hostname or "").casefold().removeprefix("www.") == home_host
        ][:2]
        for contact_url in contact_pages:
            if robots_available and not robots.can_fetch(USER_AGENT, contact_url):
                continue
            try:
                contact_html, contact_final_url = self._fetch(contact_url, ("text/html",))
            except EnrichmentFailure:
                continue
            parse_page(contact_html, contact_final_url)
            pages_checked.append(contact_final_url)

        title = " ".join(" ".join(home.title_parts).split())[:500] or None
        descriptions = [parser.description for parser in parsers if parser.description]
        return WebsiteEvidence(
            final_url=final_url,
            title=title,
            description=descriptions[0] if descriptions else None,
            public_emails=sorted({value for parser in parsers for value in parser.public_emails})[
                :10
            ],
            public_phones=sorted({value for parser in parsers for value in parser.public_phones})[
                :10
            ],
            social_links=sorted({value for parser in parsers for value in parser.social_links})[
                :10
            ],
            contact_links=sorted({value for parser in parsers for value in parser.contact_links})[
                :10
            ],
            same_host_links=sorted(
                {value for parser in parsers for value in parser.same_host_links}
            )[:100],
            pages_checked=pages_checked,
        )
