"""Acquisition channel derivation (SCA-004): one deterministic function of the facts the lead already records.

The lead keeps its ``LEAD_SOURCE`` code and the UTM, landing-page and referrer values the public form captured. This
module reduces them to one reporting channel without a marketing-attribution platform and without pretending to know
more than the record says: a website lead with neither a campaign nor a referrer is UNKNOWN (a typed address, a
messaging app, a bookmark and a blocked referrer all look the same), not "direct".
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from .vocab import CHANNELS

SOURCE_CHANNEL: dict[str, str] = {
    "REFERRAL": "REFERRAL",
    "ARCHITECT_PARTNER": "REFERRAL",
    "PHONE": "DIRECT",
    "WALK_IN": "DIRECT",
    "WHATSAPP": "DIRECT",
    "INSTAGRAM": "SOCIAL",
    "FACEBOOK": "SOCIAL",
    "GOOGLE_ADS": "PAID",
}
PAID_MEDIUMS = frozenset(
    {"cpc", "ppc", "paid", "paidsearch", "paid_search", "paidsocial", "paid_social", "display", "cpm", "ads"}
)
SOCIAL_MEDIUMS = frozenset({"social", "social_media", "organic_social"})
REFERRAL_MEDIUMS = frozenset({"referral", "partner", "affiliate"})
SOCIAL_HOSTS = ("instagram.com", "facebook.com", "fb.com", "youtube.com", "youtu.be", "linkedin.com", "pinterest.", "x.com", "twitter.com", "t.co", "threads.net", "whatsapp.com")  # fmt: skip
SEARCH_HOSTS = ("google.", "bing.com", "duckduckgo.com", "yahoo.", "search.brave.com", "ecosia.org", "yandex.")
SOCIAL_SOURCES = frozenset({"instagram", "facebook", "ig", "fb", "youtube", "linkedin", "pinterest", "twitter", "x", "threads", "whatsapp"})  # fmt: skip
SITE_HOSTS = ("vedaspaces.com",)


@dataclass(frozen=True)
class Channel:
    code: str
    detail: str  # a short, non-personal explanation of the rule that fired

    def __post_init__(self) -> None:
        assert self.code in CHANNELS


def _host(referrer: str | None) -> str | None:
    if not referrer:
        return None
    text = referrer.strip().lower()
    if "://" not in text:
        text = "https://" + text
    try:
        host = urlsplit(text).hostname or ""
    except ValueError:
        return None
    return host.removeprefix("www.") or None


def channel(source_code: str | None, utm_source: str | None = None, utm_medium: str | None = None,
            referrer: str | None = None) -> Channel:  # fmt: skip
    """The channel for a lead or an anonymous beacon. ``source_code`` is the lead's LEAD_SOURCE (WEBSITE for the site).
    ``referrer`` may be a URL or a bare host."""
    code = (source_code or "").upper()
    if code in SOURCE_CHANNEL:
        return Channel(SOURCE_CHANNEL[code], f"source {code}")
    if code not in ("WEBSITE", ""):
        return Channel("UNKNOWN", f"source {code}")
    medium = (utm_medium or "").strip().lower()
    source = (utm_source or "").strip().lower()
    if medium in PAID_MEDIUMS:
        return Channel("PAID", "campaign medium")
    if medium in SOCIAL_MEDIUMS or source in SOCIAL_SOURCES:
        return Channel("SOCIAL", "campaign source")
    if medium in REFERRAL_MEDIUMS:
        return Channel("REFERRAL", "campaign medium")
    if medium or source:
        return Channel("OTHER", "campaign")
    host = _host(referrer)
    if host is None or any(host == h or host.endswith("." + h) for h in SITE_HOSTS):
        return Channel("UNKNOWN", "no campaign, no referrer")
    if any(host == h.rstrip(".") or host.startswith(h) or host.endswith("." + h.rstrip(".")) or ("." + h) in ("." + host) for h in SEARCH_HOSTS):  # fmt: skip
        return Channel("ORGANIC_SEARCH", "search-engine referrer")
    if any(host == h.rstrip(".") or host.endswith("." + h.rstrip(".")) or host.startswith(h) for h in SOCIAL_HOSTS):
        return Channel("SOCIAL", "social referrer")
    return Channel("OTHER", "external referrer")
