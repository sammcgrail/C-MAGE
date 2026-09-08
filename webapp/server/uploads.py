"""Upload validation. Decides by content, never by file extension.

A .png that is really an HTML error page, a .pdf that is a PNG, an image that
does not decode: all rejected here with a message a person can act on, instead
of failing three minutes later inside the pipeline.
"""
from __future__ import annotations

import io
import re

from PIL import Image, ImageOps, UnidentifiedImageError

from . import config

MAX_IMAGE_PIXELS = 30_000_000        # 30 MP; larger is a decompression bomb or a scan, not a figure
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS * 2   # let PIL open it so we can reject it ourselves

IMAGE_KINDS = {"png", "jpeg", "tiff", "webp", "bmp"}


class Rejected(ValueError):
    """The upload is not something the pipeline can run. str(e) is user-facing."""


def sniff(data: bytes) -> str | None:
    head = data[:1024]
    if b"%PDF-" in head:                       # the header may follow up to 1 KB of junk
        return "pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head.startswith(b"BM"):
        return "bmp"
    return None


def safe_stem(filename: str, fallback: str) -> str:
    stem = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", filename or "")
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_")[:60]
    return stem or fallback


def pdf_pages(data: bytes) -> int:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                if reader.decrypt("") == 0:
                    raise Rejected("This PDF is password-protected; remove the password first.")
            except Rejected:
                raise
            except Exception as exc:  # noqa: BLE001
                raise Rejected("This PDF is encrypted and could not be opened.") from exc
        n = len(reader.pages)
    except Rejected:
        raise
    except (PdfReadError, ValueError, TypeError, KeyError, IndexError, RecursionError) as exc:
        raise Rejected("That file has a PDF header but could not be parsed as a PDF.") from exc
    if n < 1:
        raise Rejected("This PDF has no pages.")
    if n > config.MAX_PAGES:
        raise Rejected(f"This PDF has {n} pages; the limit here is {config.MAX_PAGES}. "
                       "Split it, or upload the pages that carry the structures as images.")
    return n


def normalize_image(data: bytes) -> tuple[bytes, int, int]:
    """Decode, sanity-check and re-encode as RGB PNG (the one format every
    stage-2 code path accepts). Returns (png_bytes, width, height)."""
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise Rejected("That image could not be decoded. PNG, JPEG, TIFF, WebP or BMP, please.") from exc
    w, h = im.size
    if w * h > MAX_IMAGE_PIXELS:
        raise Rejected(f"That image is {w}x{h}; anything over {MAX_IMAGE_PIXELS // 1_000_000} megapixels is refused.")
    if w < 32 or h < 32:
        raise Rejected(f"That image is only {w}x{h} pixels; there is nothing to segment.")
    try:
        im = ImageOps.exif_transpose(im)
    except Exception:  # noqa: BLE001 - orientation is a nicety
        pass
    if im.mode in ("RGBA", "LA", "P", "PA"):
        # Flatten transparency onto white: a transparent background reads as black.
        rgba = im.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        bg.alpha_composite(rgba)
        im = bg.convert("RGB")
    elif im.mode != "RGB":
        im = im.convert("RGB")
    out = io.BytesIO()
    im.save(out, format="PNG", optimize=False)
    return out.getvalue(), im.width, im.height


def classify(data: bytes, filename: str) -> dict:
    """Return {'kind': 'pdf'|'image', 'stem', 'pages', 'bytes', 'ext', 'width', 'height'} or raise Rejected."""
    if not data:
        raise Rejected("The upload was empty.")
    if len(data) > config.MAX_PDF_BYTES:
        raise Rejected(f"That file is {len(data) / 1e6:.1f} MB; the limit here is {config.MAX_PDF_MB:g} MB.")
    kind = sniff(data)
    if kind is None:
        looks_like_html = data[:512].lstrip().lower().startswith((b"<!doctype", b"<html", b"<?xml"))
        raise Rejected("That is an HTML page, not a document — the download probably failed." if looks_like_html
                       else "Only PDF, PNG, JPEG, TIFF, WebP or BMP files are accepted.")
    if kind == "pdf":
        return {"kind": "pdf", "stem": safe_stem(filename, "document"), "pages": pdf_pages(data),
                "bytes": data, "ext": ".pdf", "width": None, "height": None}
    png, w, h = normalize_image(data)
    return {"kind": "image", "stem": safe_stem(filename, "figure"), "pages": 1,
            "bytes": png, "ext": ".png", "width": w, "height": h}
