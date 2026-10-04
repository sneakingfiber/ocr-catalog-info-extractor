# ocr-catalog-info-extractor

Turn a product-catalog PDF into a clean, structured Excel sheet: **EAN, product code, size/variant, packaging, price**, plus category / section / product line.

It uses a **local OCR vision model** ([GLM-OCR](https://huggingface.co/zai-org/GLM-OCR) served by [Ollama](https://ollama.com)) for text recognition and a **deterministic, rule-based parser** for everything after that. There is **no cloud API, no API key, and no LLM in the parsing step**, so results are reproducible and your catalog never leaves your machine.

```
catalog.pdf
   │  pdf2image (one page at a time)
   ▼
GLM-OCR via Ollama      "Table Recognition:" prompt → plain text per page
   │
   ▼
parser.py               regex / token rules → one record per variant
   │
   ▼
classify.py             section / category / product line from a YAML profile
   │
   ▼
normalizer.py           clean, validate, de-duplicate
   │
   ▼
exporter.py             catalog_<timestamp>.xlsx
```

## Why deterministic parsing?

LLM-based extraction can silently change a digit in an EAN or invent a price. Here the OCR model only *reads* the page; the fields are then split by explicit rules. Product codes are never altered (`040742` and `40622MF` stay exactly as printed), a missing EAN stays empty instead of being guessed, and the same input always yields the same output.

## Output

One row per purchasable variant:

| Column | Source |
|---|---|
| SECTION | page range, from the profile (e.g. pages 1-60 → `BUILDING`) |
| CATEGORY | first word of the product name, looked up in the profile |
| PRODUCT LINE | regex on the product name (e.g. `line "anchor"`), formatted by the profile |
| PRODUCT NAME | text block above the table, upper-cased and whitespace-collapsed |
| EAN | 13 (or 8) digits; empty if not printed |
| PRODUCT CODE | exactly as OCR'd |
| SIZE / VARIANT | e.g. `16cm`, `28x12cm` |
| PACKAGING | e.g. `pz. 6` |
| PRICE | float; `1.204,00` and `16,61` both handled |

Duplicates are removed on `(code, size, product name)`; the same code under a different name is treated as a different product.

## Requirements

- Python 3.10+
- [poppler](https://poppler.freedesktop.org/) for `pdf2image` (`brew install poppler` / `apt install poppler-utils`)
- An [Ollama](https://ollama.com) server with the GLM-OCR model pulled (the pipeline was developed against the `glm-ocr:q8_0` tag, ~1.6 GB). The server can be local or on another machine on your network.

## Install

```bash
git clone https://github.com/<you>/ocr-catalog-info-extractor.git
cd ocr-catalog-info-extractor
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Usage

### 1. Try it without OCR

Parse the bundled synthetic OCR page; no PDF and no Ollama needed:

```bash
catalog-extract text examples/sample_ocr_page.txt --profile profiles/example.yaml --start 7
```

### 2. Run on a PDF

```bash
ollama pull glm-ocr:q8_0     # once, on the machine that runs Ollama

catalog-extract pdf catalog.pdf \
    --profile profiles/my-catalog.yaml \
    --start 7 --pages 55 \
    --ollama-url http://localhost:11434 \
    --save-ocr
```

| Flag | Default | |
|---|---|---|
| `--start` / `--pages` | `1` / `10` | 1-indexed first page and number of pages |
| `--profile` | none | YAML rules for section/category/line (see below) |
| `--ollama-url` | `$OLLAMA_URL` or `http://localhost:11434` | |
| `--model` | `$OCR_MODEL` or `glm-ocr:q8_0` | |
| `--prompt` | `Table Recognition:` | also `Text Recognition:`, `Figure Recognition:` |
| `--dpi` | `150` | PDF render resolution |
| `--save-ocr` | off | write raw OCR text and parsed JSON per page, useful for debugging |
| `--output-dir` | `output` | |

If a page's OCR request fails it is skipped and logged; the remaining pages are still exported. Use `--save-ocr` and re-run `catalog-extract text ocr_p*.txt` to re-parse without repeating the (slow) OCR step.

### 3. As a library

```python
from catalog_extractor import Profile, parse_ocr_text, classify_record, normalize, export_xlsx

profile = Profile.load("profiles/my-catalog.yaml")
records = [classify_record(r, page=7, profile=profile) for r in parse_ocr_text(ocr_text)]
export_xlsx(normalize(records), "output")
```

## Profiles

A profile is a small YAML file that teaches the extractor about *your* catalog. See [`profiles/example.yaml`](profiles/example.yaml).

```yaml
brand: ACME
sections:
  - { from_page: 1,  to_page: 60,  name: BUILDING }
  - { from_page: 61, to_page: 200, name: SITE EQUIPMENT }
category_map:            # first word of product name -> category
  TROWEL: MASON'S TOOLS
  HAMMER: HAMMERS
line_pattern: '(?:line|linea|series)\s+["'']?([A-Za-z0-9\-]+)["'']?'
line_format: '{category} - LINE "{line}" {brand}'
```

Unknown first words fall back to the word itself, so rows are never left without a category. Grow `category_map` as you discover new product families. Without `--profile`, the section and product line are left empty.

## Supported page layout

The parser targets catalogs where each product is a **name block followed by a price table** whose header row starts with `EAN CODE` (or `EAN CODICE`):

```
TROWEL ITALIAN STYLE ROUND TIP
WOODEN HANDLE - line "anchor"

EAN CODE SIZE PRICE
8 000000 000011 1000001 16cm pz. 6 16,61
```

Handled row variants: EAN + code, EAN without code, code without EAN, and the EAN printed on its own line *below* the row. Catalogs with a different table structure need a new parser module (see below).

## Extending

- **Different table layout** → add a function in `catalog_extractor/parser.py` returning the same dict keys (`product_name, ean, code, size, packaging, price`); everything downstream is unchanged.
- **Different OCR backend** → implement `recognize(PIL.Image) -> str` like `catalog_extractor/ocr.py`.
- **Different columns** → edit `models.py` and `exporter.py`.

## Development

```bash
pip install -e '.[dev]'
pytest
```

Tests use only synthetic data from `examples/`.

## Limitations

- OCR quality bounds accuracy: a misread digit in the OCR text is carried through unchanged. Spot-check prices and EANs on a few pages with `--save-ocr`.
- Only the table layout described above is supported out of the box.
- One page is sent to OCR per request; speed depends on your Ollama hardware.

## License

MIT, see [LICENSE](LICENSE).
