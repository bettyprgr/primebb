import random
import re
import string
from dataclasses import dataclass
from urllib.parse import urlparse

from app.config import get_settings

_COUNTRY_CODES = {
    "United States": "US",
    "USA": "US",
    "US": "US",
}

STATE_FULL_NAMES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}


def state_full_name(abbr: str | None) -> str | None:
    if not abbr:
        return None
    return STATE_FULL_NAMES.get(abbr.strip().upper())


@dataclass(frozen=True)
class ParsedProxy:
    proxy_url: str
    proxy_type: str
    host: str
    port: str
    username: str
    password: str


def generate_ssid(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.SystemRandom().choice(alphabet) for _ in range(length))


def country_code(country: str | None) -> str:
    if not country:
        return "US"
    country = country.strip()
    return _COUNTRY_CODES.get(country, country.upper())


def region_slug(region: str | None) -> str | None:
    if not region:
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", region.strip().lower()).strip("-")
    return slug or None


def build_proxy_url(account: dict, rotate: bool = False) -> tuple[str, str, str, str | None]:
    settings = get_settings()
    proxy_country = country_code(account.get("country") or account.get("proxy_country"))
    existing_ssid = account.get("proxy_ssid")
    ssid = generate_ssid() if rotate or not existing_ssid else existing_ssid
    saved_region_slug = region_slug(account.get("proxy_state_region")) or account.get("proxy_region_slug")

    parts = [settings.proxy_username_prefix, f"country-{proxy_country}"]
    if rotate and saved_region_slug:
        parts.append(f"st-{saved_region_slug}")
    parts.extend([f"ssid-{ssid}", f"sst-{settings.proxy_session_ttl}"])
    username = "-".join(parts)
    proxy_url = f"{username}:{settings.proxy_password}@{settings.proxy_host}:{settings.proxy_port}"
    return proxy_url, ssid, proxy_country, saved_region_slug


def parse_socks5_proxy(proxy_url: str) -> ParsedProxy:
    parsed = urlparse(f"socks5://{proxy_url}" if "://" not in proxy_url else proxy_url)
    if not parsed.hostname or not parsed.port or not parsed.username or not parsed.password:
        raise ValueError("invalid socks5 proxy")
    return ParsedProxy(
        proxy_url=proxy_url,
        proxy_type="socks5",
        host=parsed.hostname,
        port=str(parsed.port),
        username=parsed.username,
        password=parsed.password,
    )


def bitbrowser_proxy_fields(proxy_url: str) -> dict:
    proxy = parse_socks5_proxy(proxy_url)
    return {
        "proxyMethod": 2,
        "proxyType": proxy.proxy_type,
        "host": proxy.host,
        "port": proxy.port,
        "proxyUserName": proxy.username,
        "proxyPassword": proxy.password,
    }


def masked_proxy(proxy_url: str | None) -> str:
    if not proxy_url:
        return ""
    try:
        proxy = parse_socks5_proxy(proxy_url)
        return f"{proxy.username[:12]}...:***@{proxy.host}:{proxy.port}"
    except Exception:
        return "***"
