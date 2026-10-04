"""Clean, validate and deduplicate parsed product records."""

import logging
import re
from typing import Any

from .models import ProductVariant

logger = logging.getLogger(__name__)

CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{1,23}$")


def _clean_string(value: Any) -> str:
    if value is None:
        return ""
    s = "".join(c for c in str(value).strip() if c.isprintable())
    return " ".join(s.split())


def _clean_ean(value: Any):
    if value is None:
        return None
    ean = re.sub(r"\D", "", str(value))
    return ean if len(ean) in (8, 13) else None


def _clean_price(value: Any):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip().replace(",", "."))
    except ValueError:
        return None


def normalize(products: list[dict]) -> list[ProductVariant]:
    """
    Validate every record and drop duplicates.

    - Records without code or product name are skipped.
    - Codes are kept exactly as extracted (no upper-casing).
    - Dedup key: (code, size.lower(), product_name.lower()). Same code with a
      different name is a different product.
    """
    seen: dict[tuple, ProductVariant] = {}
    skipped = 0

    for p in products:
        code = _clean_string(p.get("code"))
        name = _clean_string(p.get("product_name"))
        if not code or not name or not CODE_RE.match(code):
            skipped += 1
            logger.debug("skipping record (missing/invalid code or name): %r", p)
            continue

        variant = ProductVariant(
            section=_clean_string(p.get("section")),
            category=_clean_string(p.get("category")),
            product_line=_clean_string(p.get("product_line")),
            product_name=name,
            ean=_clean_ean(p.get("ean")),
            code=code,
            size=_clean_string(p.get("size")),
            packaging=_clean_string(p.get("packaging")),
            price=_clean_price(p.get("price")),
        )
        key = (variant.code, variant.size.lower(), variant.product_name.lower())
        seen.setdefault(key, variant)

    logger.info(
        "normalized: %d in, %d skipped, %d duplicates, %d out",
        len(products), skipped, len(products) - skipped - len(seen), len(seen),
    )
    return list(seen.values())
