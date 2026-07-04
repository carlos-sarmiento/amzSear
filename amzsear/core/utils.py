"""Shared parsing and validation helpers for amzsear."""
from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable
from urllib import parse

ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
NUMBER_RE = re.compile(r"[-+]?\d[\d\s\u00a0.,']*")


def clean_text(value: object) -> str:
    """Return normalized scraped text with terminal control sequences removed."""
    text = "" if value is None else str(value)
    text = ANSI_RE.sub("", text)
    text = CONTROL_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_asin(value: object) -> str:
    """Normalize and validate an Amazon ASIN."""
    asin = clean_text(value).upper()
    if not ASIN_RE.fullmatch(asin):
        raise ValueError(f"{value!r} is not a valid 10-character ASIN")
    return asin


def is_asin(value: object) -> bool:
    """Return True if value is a syntactically valid ASIN."""
    try:
        normalize_asin(value)
    except ValueError:
        return False
    return True


def extract_asin(value: object) -> str | None:
    """Extract a 10-character ASIN from a URL or plain value."""
    text = clean_text(value)
    if is_asin(text):
        return text.upper()
    match = re.search(
        r"(?:/|%2F)(?:dp|gp/product)(?:/|%2F)([A-Z0-9]{10})(?:[/?#&]|$)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1).upper()
    return None


def is_amazon_url(value: object) -> bool:
    """Return True if value is an absolute Amazon HTTP(S) URL."""
    parsed = parse.urlparse(clean_text(value))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    host = parsed.hostname or ""
    host = host.lower()
    return host == "amazon.com" or host.startswith("amazon.") or ".amazon." in host


def validate_positive_int(value: object, name: str = "value") -> int:
    """Parse a positive integer argument."""
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if parsed < 1:
        raise ValueError(f"{name} must be a positive integer")
    return parsed


def parse_locale_number(value: object) -> float | None:
    """Parse a number using either comma or dot decimal/thousands separators."""
    text = clean_text(value)
    if not text:
        return None
    match = NUMBER_RE.search(text)
    if not match:
        return None

    token = match.group(0)
    token = token.replace("\u00a0", "").replace(" ", "").replace("'", "")
    token = re.sub(r"[^0-9,.\-+]", "", token)
    if not re.search(r"\d", token):
        return None

    sign = ""
    if token[0] in "+-":
        sign = token[0]
        token = token[1:]

    if "," in token and "." in token:
        decimal_sep = "," if token.rfind(",") > token.rfind(".") else "."
        thousands_sep = "." if decimal_sep == "," else ","
        token = token.replace(thousands_sep, "")
        token = token.replace(decimal_sep, ".")
    elif "," in token:
        token = _normalize_single_separator(token, ",")
    elif "." in token:
        token = _normalize_single_separator(token, ".")

    try:
        return float(sign + token)
    except ValueError:
        return None


def _normalize_single_separator(token: str, separator: str) -> str:
    groups = token.split(separator)
    if len(groups) == 1:
        return token
    if len(groups) > 2 and all(len(group) == 3 for group in groups[1:]):
        return "".join(groups)
    if len(groups) == 2:
        head, tail = groups
        if len(tail) == 3 and len(head) <= 3:
            return head + tail
        if separator == ",":
            return head + "." + tail
        return token
    head = "".join(groups[:-1])
    tail = groups[-1]
    if len(tail) in {1, 2}:
        return head + "." + tail
    return "".join(groups)


def extract_numbers(value: object) -> list[float]:
    """Extract all locale-aware numbers from text."""
    numbers = []
    for token in NUMBER_RE.findall(clean_text(value)):
        parsed = parse_locale_number(token)
        if parsed is not None:
            numbers.append(parsed)
    return numbers


def parse_int(value: object) -> int | None:
    """Parse a locale-aware integer from text."""
    number = parse_locale_number(value)
    if number is None:
        return None
    return int(round(number))


def parse_price_values(value: object) -> list[float]:
    """Extract numeric price values from price text."""
    prices = []
    for number in extract_numbers(value):
        if number >= 0:
            prices.append(number)
    return prices


def round_half_up(value: float) -> int:
    """Round halves away from zero for star displays."""
    return int(math.floor(value + 0.5))


def unique_preserve_order(values: Iterable[object]) -> list[object]:
    """Return unique values while preserving first occurrence order."""
    seen = set()
    unique = []
    for value in values:
        if value not in seen:
            unique.append(value)
            seen.add(value)
    return unique


def dynamic_image_urls(value: object) -> list[str]:
    """Parse Amazon's data-a-dynamic-image JSON attribute into URL strings."""
    text = clean_text(value)
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [text]
    if isinstance(data, dict):
        return [url for url in data if isinstance(url, str)]
    return []
