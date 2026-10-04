"""
Rule-based classification driven by a YAML *profile*.

A profile tells the extractor how to fill the columns the OCR text cannot provide:

  section      <- page ranges           (sections:)
  category     <- first word of name    (category_map:)
  product_line <- regex on the raw name (line_pattern: + line_format:)

See profiles/example.yaml.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

DEFAULT_LINE_PATTERN = r"""(?:line|linea|series|serie)\s+["']?([A-Za-z0-9\-]+)["']?"""
DEFAULT_LINE_FORMAT = '{category} - LINE "{line}" {brand}'


@dataclass
class Profile:
    brand: str = ""
    default_section: str = ""
    sections: list = field(default_factory=list)  # [{from_page, to_page, name}]
    category_map: dict = field(default_factory=dict)  # FIRST WORD -> CATEGORY
    line_pattern: str = DEFAULT_LINE_PATTERN
    line_format: str = DEFAULT_LINE_FORMAT

    @classmethod
    def load(cls, path: Optional[str]) -> "Profile":
        """Load a YAML profile. `None` returns an empty profile (no classification rules)."""
        if not path:
            return cls()
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls(
            brand=data.get("brand", ""),
            default_section=data.get("default_section", ""),
            sections=data.get("sections", []),
            category_map={k.upper(): v for k, v in (data.get("category_map") or {}).items()},
            line_pattern=data.get("line_pattern", DEFAULT_LINE_PATTERN),
            line_format=data.get("line_format", DEFAULT_LINE_FORMAT),
        )

    def section_for_page(self, page: int) -> str:
        for s in self.sections:
            if s["from_page"] <= page <= s["to_page"]:
                return s["name"]
        return self.default_section

    def category_for_name(self, name: str) -> str:
        words = name.strip().split()
        first = words[0].upper() if words else ""
        return self.category_map.get(first, first)

    def line_for_name(self, name: str, category: str) -> str:
        m = re.search(self.line_pattern, name, re.IGNORECASE)
        if not m:
            return category
        return self.line_format.format(
            category=category, line=m.group(1).upper(), brand=self.brand
        ).strip()


def classify_record(rec: dict, page: int, profile: Profile) -> dict:
    """Add section / category / product_line to a parsed record."""
    name = rec["product_name"]
    category = profile.category_for_name(name)
    return {
        "section": profile.section_for_page(page),
        "category": category,
        "product_line": profile.line_for_name(name, category),
        "product_name": " ".join(name.upper().split()),
        "ean": rec["ean"],
        "code": rec["code"],
        "size": rec["size"],
        "packaging": rec["packaging"],
        "price": rec["price"],
    }
