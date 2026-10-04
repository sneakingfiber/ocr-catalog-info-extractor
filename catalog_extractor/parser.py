"""
Deterministic parser for the plain-text output of glm-ocr ("Table Recognition:" prompt).

glm-ocr returns plain text (not HTML/markdown). Each product block looks like:

    PRODUCT NAME LINE 1            <- free text, 1-2 lines
    PRODUCT NAME LINE 2
    [blank line]
    EAN CODE SIZE PRICE            <- header row (skipped)
    8 000000 000011 1000001 16cm pz. 6 16,61     <- data row
    8 000000 000028 1000002 18cm pz. 6 17,06
    [blank line -> next block]

Data-row variants handled:
  - EAN (3 groups) + CODE + SIZE + PACKAGING + PRICE
  - EAN (3 groups) + SIZE + PACKAGING + PRICE            (no code)
  - CODE + SIZE + PACKAGING + PRICE                      (no EAN)
  - "format B": the EAN sits alone on the line *below* its data row

Codes are never modified (no upper-casing, no stripping of leading zeros).
No LLM is involved: everything is regex/token logic.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Table header row: starts with "EAN" followed by "CODE"/"CODICE"
HEADER_RE = re.compile(r"^\s*EAN\s+(CODE|CODICE)", re.IGNORECASE)


def _is_size(token: str) -> bool:
    """True if the token looks like a size ("16cm", "28x12", "5mm"), not a product code."""
    t = token.upper()
    return bool(t.endswith("CM") or t.endswith("MM") or re.match(r"^\d+X\d+", t))


def _clean_ean(raw: str) -> Optional[str]:
    digits = re.sub(r"\D", "", raw)
    return digits if len(digits) in (8, 13) else None


def parse_price(raw: str) -> Optional[float]:
    """Parse European ("1.234,56", "16,61") and plain ("16.61") prices to float."""
    s = raw.strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except (ValueError, AttributeError):
        return None


def _parse_data_row(tokens: list) -> Optional[dict]:
    """Parse one data row into its fields, or return None if it is not a data row."""
    if not tokens:
        return None

    ean_raw = None
    code = None
    rest = tokens

    # EAN printed as 3 groups, e.g. "8 021636 210023"
    if len(tokens) >= 3 and len(tokens[0]) == 1 and tokens[0].isdigit():
        combined = tokens[0] + tokens[1] + tokens[2]
        if len(re.sub(r"\D", "", combined)) == 13:
            ean_raw = " ".join(tokens[:3])
            after_ean = tokens[3:]
            if not after_ean:
                return None
            if _is_size(after_ean[0]):
                code, rest = None, after_ean
            else:
                code, rest = after_ean[0], after_ean[1:]

    if ean_raw is None:
        code = tokens[0]
        rest = tokens[1:]

    # rest = [SIZE, PACKAGING..., PRICE]  -> at least 3 tokens
    if len(rest) < 3:
        return None

    price = parse_price(rest[-1])
    if price is None:
        return None

    return {
        "ean": _clean_ean(ean_raw) if ean_raw else None,
        "code": code,
        "size": rest[0],
        "packaging": " ".join(rest[1:-1]),
        "price": price,
    }


def parse_ocr_text(raw_text: str) -> list[dict]:
    """
    Parse glm-ocr plain text into records with keys:
    product_name, ean, code, size, packaging, price.
    """
    lines = [l.rstrip() for l in raw_text.split("\n")]
    records: list[dict] = []
    i = 0

    while i < len(lines):
        if HEADER_RE.match(lines[i]):
            # Product name = non-blank lines right above the header
            name_lines = []
            j = i - 1
            while j >= 0 and not lines[j].strip():
                j -= 1
            while j >= 0 and lines[j].strip():
                name_lines.insert(0, lines[j].strip())
                j -= 1
            product_name = "\n".join(name_lines) if name_lines else None

            i += 1
            while i < len(lines):
                data_line = lines[i].strip()
                if not data_line:
                    break  # end of table
                tokens = data_line.split()

                # Format B: a line made only of digits = EAN of the previous row
                combined = re.sub(r"\D", "", data_line)
                if all(t.isdigit() for t in tokens) and len(combined) in (8, 13):
                    if records and records[-1].get("ean") is None:
                        records[-1]["ean"] = combined
                    i += 1
                    continue

                parsed = _parse_data_row(tokens)
                if parsed and product_name:
                    records.append({"product_name": product_name, **parsed})
                i += 1
        i += 1

    logger.debug("parser: %d records", len(records))
    return records
