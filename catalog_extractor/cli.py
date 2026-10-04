"""Command line interface: `catalog-extract pdf ...` and `catalog-extract text ...`."""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from tqdm import tqdm

from .classify import Profile, classify_record
from .exporter import export_xlsx
from .normalizer import normalize
from .ocr import PROMPTS, OllamaOCR
from .parser import parse_ocr_text

logger = logging.getLogger("catalog_extractor")


def _finish(products: list[dict], output_dir: str) -> None:
    final = normalize(products)
    path = export_xlsx(final, output_dir)
    print(f"\n{len(final)} products -> {path}")


def cmd_pdf(args) -> None:
    from pdf2image import convert_from_path

    profile = Profile.load(args.profile)
    ocr = OllamaOCR(url=args.ollama_url, model=args.model, prompt=args.prompt)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    last = args.start + args.pages - 1
    images = convert_from_path(args.pdf, dpi=args.dpi, first_page=args.start, last_page=last)

    products: list[dict] = []
    for offset, img in enumerate(tqdm(images, unit="page")):
        page = args.start + offset
        try:
            text = ocr.recognize(img)
        except requests.exceptions.RequestException as e:
            tqdm.write(f"page {page}: OCR failed: {e}")
            continue
        if args.save_ocr:
            (out_dir / f"ocr_p{page:03d}_{stamp}.txt").write_text(text, encoding="utf-8")
        records = [classify_record(r, page, profile) for r in parse_ocr_text(text)]
        if args.save_ocr and records:
            (out_dir / f"parsed_p{page:03d}_{stamp}.json").write_text(
                json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        tqdm.write(f"page {page}: {len(records)} records")
        products.extend(records)

    _finish(products, args.output_dir)


def cmd_text(args) -> None:
    """Parse already-OCR'd text files (no PDF, no Ollama needed)."""
    profile = Profile.load(args.profile)
    products: list[dict] = []
    for i, f in enumerate(args.files):
        page = args.start + i
        text = Path(f).read_text(encoding="utf-8")
        records = [classify_record(r, page, profile) for r in parse_ocr_text(text)]
        print(f"{f}: {len(records)} records")
        products.extend(records)
    _finish(products, args.output_dir)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="catalog-extract", description=__doc__)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--profile", help="YAML profile with categories/sections (see profiles/example.yaml)")
    common.add_argument("--output-dir", default="output")
    common.add_argument("--start", type=int, default=1, help="first page, 1-indexed (default: 1)")

    pdf = sub.add_parser("pdf", parents=[common], help="OCR a PDF and export to Excel")
    pdf.add_argument("pdf", help="path to the catalog PDF")
    pdf.add_argument("--pages", type=int, default=10, help="number of pages to process (default: 10)")
    pdf.add_argument("--dpi", type=int, default=150)
    pdf.add_argument("--ollama-url", default=os.getenv("OLLAMA_URL", "http://localhost:11434"))
    pdf.add_argument("--model", default=os.getenv("OCR_MODEL", "glm-ocr:q8_0"))
    pdf.add_argument("--prompt", default="Table Recognition:", choices=PROMPTS)
    pdf.add_argument("--save-ocr", action="store_true", help="also save raw OCR text and parsed JSON per page")
    pdf.set_defaults(func=cmd_pdf)

    txt = sub.add_parser("text", parents=[common], help="parse OCR text files (one file per page)")
    txt.add_argument("files", nargs="+")
    txt.set_defaults(func=cmd_text)
    return p


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    try:
        args.func(args)
    except FileNotFoundError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
