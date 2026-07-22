from __future__ import annotations

import hashlib
import hmac
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, Protocol
from urllib.parse import quote, urlparse

import httpx

from app.core.config import Settings
from app.db.models import Campaign
from app.domains.automation.enrichment import EnrichmentFailure, SafeWebsiteEnricher
from app.domains.leads.identity import social_identity, valid_public_email
from app.domains.system.meta import MetaConnectionService, MetaProviderCredentials


class ProviderFailure(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message


@dataclass(frozen=True)
class DiscoveredBusiness:
    provider_record_id: str
    business_name: str
    location: str
    website: str | None
    phone: str | None
    source_url: str | None
    latitude: float | None
    longitude: float | None
    place_types: list[str]
    evidence: dict[str, Any]


@dataclass(frozen=True)
class DiscoveryBatch:
    businesses: list[DiscoveredBusiness]
    queries: list[str]
    request_count: int
    warnings: list[str] | None = None


class DiscoveryProvider(Protocol):
    def discover(self, campaign: Campaign) -> DiscoveryBatch: ...


@dataclass(frozen=True)
class InstagramProfessionalProfile:
    account_id: str
    username: str
    profile_url: str
    business_name: str
    biography: str | None
    website: str | None
    public_email: str | None
    public_phone: str | None
    followers_count: int | None
    media_count: int | None


def _distance_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_miles = 3958.8
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    return earth_radius_miles * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


class GooglePlacesProvider:
    name = "google_places"
    _GEOCODE_URL = "https://geocode.googleapis.com/v4/geocode/address"
    _SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
    _SEARCH_FIELDS = ",".join(
        (
            "places.id",
            "places.displayName",
            "places.formattedAddress",
            "places.location",
            "places.types",
            "places.websiteUri",
            "places.nationalPhoneNumber",
            "places.internationalPhoneNumber",
            "places.businessStatus",
            "places.googleMapsUri",
        )
    )

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.Client(
            timeout=settings.provider_timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        )

    def _headers(self, field_mask: str) -> dict[str, str]:
        api_key = self.settings.google_places_api_key
        if not self.settings.google_places_enabled or api_key is None:
            raise ProviderFailure(
                "GOOGLE_PLACES_NOT_CONFIGURED",
                "Google Places discovery is not configured; existing leads were still refreshed.",
            )
        return {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key.get_secret_value(),
            "X-Goog-FieldMask": field_mask,
        }

    def _geocode(self, location: str) -> tuple[float, float]:
        url = f"{self._GEOCODE_URL}/{quote(location, safe='')}"
        try:
            response = self.client.get(
                url,
                headers=self._headers("results.location,results.formattedAddress"),
                params={"regionCode": "gb"},
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            point = results[0]["location"] if results else None
            if not point:
                raise ProviderFailure(
                    "CAMPAIGN_LOCATION_NOT_FOUND",
                    "The campaign location could not be resolved by the configured provider.",
                )
            return float(point["latitude"]), float(point["longitude"])
        except ProviderFailure:
            raise
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise ProviderFailure(
                "GOOGLE_GEOCODING_FAILED",
                "The configured provider could not resolve the campaign location.",
            ) from exc

    def discover(self, campaign: Campaign) -> DiscoveryBatch:
        center_latitude, center_longitude = self._geocode(campaign.primary_location)
        search_terms = campaign.keywords or [campaign.segment]
        search_terms = search_terms[: self.settings.discovery_max_queries]
        result_by_id: dict[str, DiscoveredBusiness] = {}
        queries: list[str] = []
        request_count = 1
        remaining = self.settings.discovery_max_results
        for term in search_terms:
            if remaining <= 0:
                break
            query = f"{term} in {campaign.primary_location}"
            queries.append(query)
            body: dict[str, Any] = {
                "textQuery": query,
                "pageSize": min(20, remaining),
                "languageCode": "en",
                "regionCode": "GB",
                "locationBias": {
                    "circle": {
                        "center": {
                            "latitude": center_latitude,
                            "longitude": center_longitude,
                        },
                        "radius": min(campaign.radius_miles * 1609.344, 50_000),
                    }
                },
            }
            try:
                response = self.client.post(
                    self._SEARCH_URL,
                    headers=self._headers(self._SEARCH_FIELDS),
                    json=body,
                )
                request_count += 1
                response.raise_for_status()
                places = response.json().get("places", [])
            except (httpx.HTTPError, TypeError, ValueError) as exc:
                raise ProviderFailure(
                    "GOOGLE_PLACES_SEARCH_FAILED",
                    "Google Places discovery failed without changing existing lead data.",
                ) from exc
            for place in places:
                if place.get("businessStatus") == "CLOSED_PERMANENTLY":
                    continue
                point = place.get("location") or {}
                latitude = point.get("latitude")
                longitude = point.get("longitude")
                if latitude is not None and longitude is not None:
                    distance = _distance_miles(
                        center_latitude,
                        center_longitude,
                        float(latitude),
                        float(longitude),
                    )
                    if distance > campaign.radius_miles:
                        continue
                place_id = str(place.get("id", "")).strip()
                name = str((place.get("displayName") or {}).get("text", "")).strip()
                address = str(place.get("formattedAddress", "")).strip()
                if not place_id or not name or not address:
                    continue
                result_by_id[place_id] = DiscoveredBusiness(
                    provider_record_id=place_id,
                    business_name=name,
                    location=address,
                    website=str(place["websiteUri"]) if place.get("websiteUri") else None,
                    phone=(
                        str(place.get("internationalPhoneNumber") or place["nationalPhoneNumber"])
                        if place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber")
                        else None
                    ),
                    source_url=(
                        str(place["googleMapsUri"]) if place.get("googleMapsUri") else None
                    ),
                    latitude=float(latitude) if latitude is not None else None,
                    longitude=float(longitude) if longitude is not None else None,
                    place_types=[str(value) for value in place.get("types", [])],
                    evidence={
                        "business_status": place.get("businessStatus", "OPERATIONAL"),
                        "distance_miles": round(distance, 2)
                        if latitude is not None and longitude is not None
                        else None,
                        "query": query,
                    },
                )
                remaining = self.settings.discovery_max_results - len(result_by_id)
                if remaining <= 0:
                    break
        return DiscoveryBatch(
            businesses=list(result_by_id.values()),
            queries=queries,
            request_count=request_count,
        )


_EMAIL_PATTERN = re.compile(r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", re.I)
_PHONE_PATTERN = re.compile(r"(?<!\w)(\+?[0-9][0-9() .-]{7,}[0-9])(?!\w)")


def _public_email_from_text(value: str) -> str | None:
    for match in _EMAIL_PATTERN.findall(value):
        # re.Pattern.findall's return type is not group-count-aware, so typeshed
        # types `match` as Any; str() pins it back down to a concrete type.
        candidate = str(match).casefold()
        if valid_public_email(candidate):
            return candidate
    return None


def _public_phone_from_text(value: str) -> str | None:
    match = _PHONE_PATTERN.search(value)
    return match.group(1).strip() if match else None


class MetaInstagramProvider:
    name = "instagram"

    def __init__(
        self,
        settings: Settings,
        connection_service: MetaConnectionService,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self.connection_service = connection_service
        self.client = client or httpx.Client(
            timeout=settings.provider_timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        )

    @property
    def connected(self) -> bool:
        return self.connection_service.status().connected

    @staticmethod
    def _proof(credentials: MetaProviderCredentials) -> str:
        return hmac.new(
            credentials.app_secret.encode("utf-8"),
            credentials.page_access_token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _get(
        self,
        credentials: MetaProviderCredentials,
        path: str,
        params: dict[str, str],
    ) -> dict[str, Any]:
        url = f"https://graph.facebook.com/{self.settings.meta_graph_version}/{path.lstrip('/')}"
        request_params = {
            **params,
            "access_token": credentials.page_access_token,
            "appsecret_proof": self._proof(credentials),
        }
        try:
            response = self.client.get(url, params=request_params)
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderFailure(
                "META_INSTAGRAM_UNAVAILABLE",
                "Instagram profile lookup could not reach Meta; existing lead data was retained.",
            ) from exc
        if response.is_error or not isinstance(payload, dict) or payload.get("error"):
            error = payload.get("error", {}) if isinstance(payload, dict) else {}
            error_code = str(error.get("code", "unknown")) if isinstance(error, dict) else "unknown"
            raise ProviderFailure(
                "META_INSTAGRAM_API_ERROR",
                "Meta rejected the Instagram profile lookup. Check the connection and basic "
                f"Instagram/Page permissions (Meta error {error_code}).",
            )
        return payload

    def _business_profile(
        self, credentials: MetaProviderCredentials, username: str
    ) -> dict[str, Any]:
        fields = (
            f"business_discovery.username({username})"
            "{id,username,name,biography,website,followers_count,media_count}"
        )
        payload = self._get(
            credentials,
            credentials.instagram_account_id,
            {"fields": fields},
        )
        value = payload.get("business_discovery")
        if not isinstance(value, dict):
            raise ProviderFailure(
                "META_INSTAGRAM_PROFILE_UNAVAILABLE",
                "Meta did not expose this Instagram account as a professional profile.",
            )
        return value

    def lookup_profile(self, profile_url: str) -> InstagramProfessionalProfile:
        """Resolve one operator-selected professional profile through Business Discovery."""
        try:
            _, username, canonical_url = social_identity(profile_url, "instagram")
        except ValueError as exc:
            raise ProviderFailure(
                "META_INSTAGRAM_PROFILE_URL_INVALID",
                "Provide a public Instagram business profile URL, not a post or hashtag page.",
            ) from exc
        try:
            credentials = self.connection_service.provider_credentials()
        except Exception as exc:
            raise ProviderFailure(
                "META_INSTAGRAM_NOT_CONNECTED",
                "Connect an Instagram professional account in Settings before looking up profiles.",
            ) from exc
        try:
            value = self._business_profile(credentials, username)
        except ProviderFailure as exc:
            if exc.code == "META_INSTAGRAM_API_ERROR":
                raise ProviderFailure(
                    "META_INSTAGRAM_PROFILE_UNAVAILABLE",
                    f"Meta could not expose @{username}. Confirm the handle and that it is a "
                    "public Instagram professional account.",
                ) from exc
            raise

        account_id = str(value.get("id", "")).strip()
        resolved_username = str(value.get("username", username)).strip().casefold()
        if not account_id or not resolved_username:
            raise ProviderFailure(
                "META_INSTAGRAM_PROFILE_UNAVAILABLE",
                f"Meta did not expose @{username} as an Instagram professional account.",
            )
        biography = str(value.get("biography", "")).strip() or None
        website = str(value.get("website", "")).strip() or None
        return InstagramProfessionalProfile(
            account_id=account_id,
            username=resolved_username,
            profile_url=(
                f"https://www.instagram.com/{resolved_username}"
                if resolved_username != username
                else canonical_url
            ),
            business_name=str(value.get("name", "")).strip() or resolved_username,
            biography=biography,
            website=website,
            public_email=_public_email_from_text(biography or ""),
            public_phone=_public_phone_from_text(biography or ""),
            followers_count=(
                int(value["followers_count"]) if value.get("followers_count") is not None else None
            ),
            media_count=int(value["media_count"]) if value.get("media_count") is not None else None,
        )

    @staticmethod
    def profile_business(
        profile: InstagramProfessionalProfile, campaign: Campaign
    ) -> DiscoveredBusiness:
        return DiscoveredBusiness(
            provider_record_id=profile.account_id,
            business_name=profile.business_name,
            location=campaign.primary_location,
            website=profile.website,
            phone=profile.public_phone,
            source_url=profile.profile_url,
            latitude=None,
            longitude=None,
            place_types=["instagram_professional", campaign.segment],
            evidence={
                "social_profile": {
                    "platform": "instagram",
                    "profile_url": profile.profile_url,
                    "handle": profile.username,
                    "public_email": profile.public_email,
                    "public_bio": profile.biography,
                    "capture_method": "official_meta_business_discovery",
                },
                "instagram": {
                    "account_id": profile.account_id,
                    "followers_count": profile.followers_count,
                    "media_count": profile.media_count,
                    "location_basis": "selected campaign context",
                    "exact_radius_verified": False,
                },
            },
        )


_SYSTEMIC_INSTAGRAM_FAILURE_CODES = {"META_INSTAGRAM_UNAVAILABLE", "META_INSTAGRAM_NOT_CONNECTED"}
_MAX_HANDLE_LENGTH = 30


def generate_handle_guesses(business_name: str, town: str = "") -> list[str]:
    """Derive a small, bounded set of plausible Instagram handles for a business name.

    Every guess is only ever a candidate URL for `MetaInstagramProvider.lookup_profile` to
    verify through the official Business Discovery API - nothing here asserts an account exists.
    """
    name_compact = re.sub(r"[^a-z0-9]", "", business_name.casefold())
    name_snake = re.sub(r"[^a-z0-9]+", "_", business_name.casefold()).strip("_")
    town_compact = re.sub(r"[^a-z0-9]", "", town.casefold()) if town else ""
    ordered_guesses = [name_compact, name_snake]
    if town_compact:
        ordered_guesses.append(f"{name_compact}{town_compact}")
        ordered_guesses.append(f"{name_snake}_{town_compact}")
    seen: set[str] = set()
    handles: list[str] = []
    for guess in ordered_guesses:
        if guess and guess not in seen and len(guess) <= _MAX_HANDLE_LENGTH:
            seen.add(guess)
            handles.append(guess)
    return [f"https://www.instagram.com/{handle}" for handle in handles[:4]]


class FhrsInstagramProvider:
    """Resolves UK Food Standards Agency registrations to verified Instagram profiles.

    FHRS (https://api.ratings.food.gov.uk) is free, keyless, official UK government data
    covering every food business registered with a local authority - including home bakers
    and caterers with no website or Google Places listing, since UK law requires anyone
    selling food, even from a home kitchen, to register. This provider only ever generates
    *candidate* handles from a business name; every identity is still resolved exclusively
    through `MetaInstagramProvider.lookup_profile` (see ADR-016/ADR-017).
    """

    name = "fhrs"
    _ESTABLISHMENTS_URL = "https://api.ratings.food.gov.uk/Establishments"
    _RATE_LIMIT_GUARD_THRESHOLD = 12

    def __init__(
        self,
        settings: Settings,
        instagram_provider: MetaInstagramProvider,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self.instagram_provider = instagram_provider
        self.client = client or httpx.Client(
            timeout=settings.provider_timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        )

    def _search(self, campaign: Campaign) -> list[dict[str, Any]]:
        # FHRS's `address` search does a near-exact match against its own text index rather
        # than a fuzzy/tokenised one - "Luton, United Kingdom" (this app's own placeholder
        # format) returns zero results even though "Luton" alone returns thousands, so only
        # the first comma-separated segment (the town/city) is sent.
        location_query = campaign.primary_location.split(",", 1)[0].strip()
        try:
            response = self.client.get(
                self._ESTABLISHMENTS_URL,
                params={
                    "address": location_query,
                    "pageSize": self.settings.fhrs_max_businesses_per_run,
                    "pageNumber": 1,
                },
                headers={"x-api-version": "2", "accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderFailure(
                "FHRS_UNAVAILABLE",
                "The Food Standards Agency register could not be reached; existing lead data "
                "was retained.",
            ) from exc
        establishments = payload.get("establishments") if isinstance(payload, dict) else None
        return establishments if isinstance(establishments, list) else []

    @staticmethod
    def _relevant(establishment: dict[str, Any], terms: frozenset[str]) -> bool:
        if not terms:
            return True
        haystack = " ".join(
            str(establishment.get(field, "")) for field in ("BusinessName", "BusinessType")
        ).casefold()
        return any(term in haystack for term in terms)

    def discover(self, campaign: Campaign) -> DiscoveryBatch:
        if not self.instagram_provider.connected:
            raise ProviderFailure(
                "META_INSTAGRAM_NOT_CONNECTED",
                "Connect an Instagram professional account in Settings before running public "
                "registry discovery.",
            )
        establishments = self._search(campaign)
        terms = frozenset(
            value.casefold() for value in (*campaign.keywords, campaign.segment) if value
        )
        matched = [item for item in establishments if self._relevant(item, terms)]

        businesses: list[DiscoveredBusiness] = []
        warnings: list[str] = []
        request_count = 1
        lookups_used = 0
        consecutive_misses = 0
        for index, establishment in enumerate(matched):
            if lookups_used >= self.settings.fhrs_max_instagram_lookups_per_run:
                warnings.append(
                    "Instagram lookup budget exhausted; "
                    f"{len(matched) - index} FHRS matches were not attempted."
                )
                break
            name = str(establishment.get("BusinessName", "")).strip()
            if not name:
                continue
            town = str(
                establishment.get("AddressLine3")
                or establishment.get("AddressLine2")
                or establishment.get("AddressLine1")
                or ""
            ).strip()
            postcode = str(establishment.get("PostCode", "")).strip()
            guesses = generate_handle_guesses(name, town)[
                : self.settings.fhrs_handle_guesses_per_business
            ]
            matches: list[InstagramProfessionalProfile] = []
            stop_run = False
            for guess_url in guesses:
                if lookups_used >= self.settings.fhrs_max_instagram_lookups_per_run:
                    break
                lookups_used += 1
                request_count += 1
                try:
                    matches.append(self.instagram_provider.lookup_profile(guess_url))
                except ProviderFailure as exc:
                    if exc.code in _SYSTEMIC_INSTAGRAM_FAILURE_CODES:
                        raise
                    consecutive_misses += 1
                    if consecutive_misses >= self._RATE_LIMIT_GUARD_THRESHOLD:
                        warnings.append(
                            "Stopped early after repeated unresolved Instagram lookups; this "
                            "may reflect Meta rate-limiting rather than an absence of matches."
                        )
                        stop_run = True
                        break
                    continue
                consecutive_misses = 0
                # A hit on an earlier, more-likely guess is taken as sufficient - trying the
                # remaining guesses would only spend more of the lookup budget without reducing
                # the risk of a coincidental false match, since that risk lives in the guess
                # itself, not in how many more are tried afterwards.
                break
            if stop_run:
                break
            if matches:
                business = MetaInstagramProvider.profile_business(matches[0], campaign)
                # FHRS gives a real registered address, unlike a bare Instagram lookup - use it
                # in preference to the generic campaign location the base profile carries.
                fhrs_location = ", ".join(part for part in (town, postcode) if part)
                businesses.append(
                    replace(
                        business,
                        location=fhrs_location or business.location,
                        evidence={
                            **business.evidence,
                            "fhrs": {
                                "fhrsid": establishment.get("FHRSID"),
                                "postcode": postcode,
                                "matched_handle": matches[0].username,
                            },
                        },
                    )
                )
            else:
                warnings.append(f"No Instagram match for {name}, {postcode} (FHRS).")
        location_query = campaign.primary_location.split(",", 1)[0].strip()
        return DiscoveryBatch(
            businesses=businesses,
            queries=[f"FHRS establishments near {location_query}"],
            request_count=request_count,
            warnings=warnings,
        )


@dataclass(frozen=True)
class _EventDirectoryEntry:
    directory_url: str
    supplier_path_prefix: str
    label: str


# Deliberately small and manually verified rather than guessed: each entry's page structure
# was confirmed before being added. Extend by adding another verified entry, not by guessing
# a commercial site's URL pattern from memory.
_EVENT_DIRECTORY_CATALOG: tuple[_EventDirectoryEntry, ...] = (
    _EventDirectoryEntry(
        directory_url="https://www.weddings.suffolk.gov.uk/suppliers-directory/wedding-planners/",
        supplier_path_prefix="/suppliers-directory/wedding-planners/",
        label="Suffolk Registration Service supplier directory",
    ),
)


class EventDirectoryProvider:
    """Resolves home-based event/wedding planners via curated public directory pages.

    There is no legal registration requirement pulling unincorporated event/wedding planners
    into a government database the way UK food-hygiene law does for FHRS, so the closest public
    equivalent is the directory pages councils and marketplaces already publish. This performs a
    two-hop fetch (directory listing -> each listed supplier's own page) using the same
    robots.txt-respecting, SSRF-hardened `SafeWebsiteEnricher` already used for business
    websites, then verifies every discovered Instagram link through the official Business
    Discovery API - never Instagram itself.
    """

    name = "event_directories"
    _MAX_SUPPLIER_PAGES_PER_DIRECTORY = 20

    def __init__(
        self,
        settings: Settings,
        instagram_provider: MetaInstagramProvider,
        enricher: SafeWebsiteEnricher,
    ) -> None:
        self.settings = settings
        self.instagram_provider = instagram_provider
        self.enricher = enricher

    @staticmethod
    def _is_instagram_link(link: str) -> bool:
        host = (urlparse(link).hostname or "").casefold()
        return host in {"instagram.com", "www.instagram.com"}

    def discover(self, campaign: Campaign) -> DiscoveryBatch:
        if not self.instagram_provider.connected:
            raise ProviderFailure(
                "META_INSTAGRAM_NOT_CONNECTED",
                "Connect an Instagram professional account in Settings before running public "
                "registry discovery.",
            )
        candidate_links: dict[str, str] = {}
        warnings: list[str] = []
        queries: list[str] = []
        request_count = 0
        for entry in _EVENT_DIRECTORY_CATALOG:
            queries.append(entry.directory_url)
            try:
                directory_evidence = self.enricher.enrich(entry.directory_url)
            except EnrichmentFailure as exc:
                warnings.append(f"{entry.label}: {exc.safe_message}")
                continue
            request_count += 1
            prefix = entry.supplier_path_prefix.rstrip("/")
            supplier_pages = [
                link
                for link in directory_evidence.same_host_links
                if urlparse(link).path.startswith(entry.supplier_path_prefix)
                and urlparse(link).path.rstrip("/") != prefix
            ][: self._MAX_SUPPLIER_PAGES_PER_DIRECTORY]
            for supplier_url in supplier_pages:
                try:
                    supplier_evidence = self.enricher.enrich(supplier_url)
                except EnrichmentFailure:
                    continue
                request_count += 1
                for link in supplier_evidence.social_links:
                    if self._is_instagram_link(link):
                        candidate_links.setdefault(link, supplier_url)

        limited_links = list(candidate_links.items())
        if len(limited_links) > self.settings.registry_max_instagram_candidates:
            warnings.append(
                "Found more Instagram candidates than the safe limit "
                f"({self.settings.registry_max_instagram_candidates}); extra candidates were "
                "skipped."
            )
            limited_links = limited_links[: self.settings.registry_max_instagram_candidates]

        businesses: list[DiscoveredBusiness] = []
        for link, source_page in limited_links:
            request_count += 1
            try:
                profile = self.instagram_provider.lookup_profile(link)
            except ProviderFailure as exc:
                if exc.code in _SYSTEMIC_INSTAGRAM_FAILURE_CODES:
                    raise
                warnings.append(f"{link}: {exc.safe_message}")
                continue
            business = MetaInstagramProvider.profile_business(profile, campaign)
            businesses.append(
                replace(
                    business,
                    evidence={**business.evidence, "event_directory": {"source_url": source_page}},
                )
            )
        return DiscoveryBatch(
            businesses=businesses, queries=queries, request_count=request_count, warnings=warnings
        )


_REGISTRY_MATCHERS: tuple[tuple[str, frozenset[str]], ...] = (
    (
        "fhrs",
        frozenset(
            {
                "baker",
                "bakery",
                "cake",
                "patisserie",
                "caterer",
                "catering",
                "confectioner",
                "pastry",
                "food",
            }
        ),
    ),
    (
        "event_directories",
        frozenset(
            {
                "wedding",
                "event planner",
                "party planner",
                "event stylist",
                "event styling",
                "celebrant",
            }
        ),
    ),
)


class PublicRegistryProvider:
    """Routes a campaign to whichever registry sources match its segment/keywords.

    The operator selects "Public registries & directories" once per campaign; which
    underlying registries actually run (FHRS, event directories, anything added later) is
    engineering-owned routing logic in `_REGISTRY_MATCHERS`, not per-campaign configuration.
    """

    name = "public_registries"

    def __init__(
        self,
        settings: Settings,
        instagram_provider: MetaInstagramProvider,
        enricher: SafeWebsiteEnricher | None = None,
    ) -> None:
        self.settings = settings
        self.instagram_provider = instagram_provider
        self.enricher = enricher or SafeWebsiteEnricher(settings)
        self._factories: dict[str, Callable[[], DiscoveryProvider]] = {
            "fhrs": lambda: FhrsInstagramProvider(self.settings, self.instagram_provider),
            "event_directories": lambda: EventDirectoryProvider(
                self.settings, self.instagram_provider, self.enricher
            ),
        }

    def _matched_registries(self, campaign: Campaign) -> list[str]:
        haystack = " ".join(
            (*campaign.keywords, campaign.segment, *campaign.product_categories)
        ).casefold()
        return [
            name for name, terms in _REGISTRY_MATCHERS if any(term in haystack for term in terms)
        ]

    def discover(self, campaign: Campaign) -> DiscoveryBatch:
        matched = self._matched_registries(campaign)
        if not matched:
            return DiscoveryBatch(
                businesses=[],
                queries=[],
                request_count=0,
                warnings=[
                    "No public registry source matches this campaign's segment/keywords yet."
                ],
            )
        businesses: list[DiscoveredBusiness] = []
        queries: list[str] = []
        warnings: list[str] = []
        request_count = 0
        for registry_name in matched:
            provider = self._factories[registry_name]()
            try:
                batch = provider.discover(campaign)
            except ProviderFailure as exc:
                if exc.code in _SYSTEMIC_INSTAGRAM_FAILURE_CODES:
                    raise
                warnings.append(f"{registry_name}: {exc.safe_message}")
                continue
            businesses.extend(batch.businesses)
            queries.extend(batch.queries)
            request_count += batch.request_count
            warnings.extend(batch.warnings or [])
        return DiscoveryBatch(
            businesses=businesses, queries=queries, request_count=request_count, warnings=warnings
        )
