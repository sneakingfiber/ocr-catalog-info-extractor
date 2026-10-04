from dataclasses import dataclass, fields
from typing import Optional


@dataclass
class ProductVariant:
    """One row of the output spreadsheet: a single purchasable variant."""

    section: str = ""
    category: str = ""
    product_line: str = ""
    product_name: str = ""
    ean: Optional[str] = None
    code: str = ""
    size: str = ""
    packaging: str = ""
    price: Optional[float] = None


COLUMN_ORDER = [f.name for f in fields(ProductVariant)]

COLUMN_HEADERS = {
    "section": "SECTION",
    "category": "CATEGORY",
    "product_line": "PRODUCT LINE",
    "product_name": "PRODUCT NAME",
    "ean": "EAN",
    "code": "PRODUCT CODE",
    "size": "SIZE / VARIANT",
    "packaging": "PACKAGING",
    "price": "PRICE",
}
