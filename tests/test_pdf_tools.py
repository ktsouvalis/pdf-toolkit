import io
import os
import sys
import math
import tempfile
import pytest
import fitz  # PyMuPDF
from PIL import Image

# Ensure project root is importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import merge_pdf
import split_pdf as splitter
from shrink_scanned_pdf import compress_scanned_pdf


# ---------- Helpers ----------

def make_text_pdf(path: str, pages: int = 3, base_text: str = "Hello") -> str:
    doc = fitz.open()
    try:
        for i in range(pages):
            p = doc.new_page(width=595, height=842)  # A4 points
            text = f"{base_text} page {i+1}/{pages}"
            p.insert_text((72, 100 + 24 * i), text, fontsize=16)
        doc.save(path)
    finally:
        doc.close()
    return path


def make_scanned_like_pdf(path: str, pages: int = 2, size=(2000, 2600)) -> str:
    # Create a large PNG image (lossless) to simulate a scanned page
    # Alternate colors per page to avoid exact duplicate streams
    doc = fitz.open()
    try:
        for i in range(pages):
            img = Image.new("RGB", size, color=(230 - 30 * (i % 3), 230, 230))
            # draw some lines to add detail
            for y in range(0, size[1], 200):
                for x in range(0, size[0], 200):
                    img.putpixel((x, y), (10 * (i + 1), 100, 150))
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            data = buf.getvalue()
            buf.close()

            # Page at A4 size
            page = doc.new_page(width=595, height=842)
            rect = page.rect
            page.insert_image(rect, stream=data)
        doc.save(path)
    finally:
        doc.close()
    return path


# ---------- Tests: merge ----------

def test_merge_basic(tmp_path):
    a = make_text_pdf(tmp_path / "a.pdf", pages=1)
    b = make_text_pdf(tmp_path / "b.pdf", pages=2)

    # set metadata on first to verify propagation
    with fitz.open(a) as d:
        d.set_metadata({"title": "FirstDoc", "author": "UnitTest"})
        a_with_meta = tmp_path / "a_with_meta.pdf"
        d.save(a_with_meta)

    out = tmp_path / "merged.pdf"
    result = merge_pdf.merge_pdfs([str(a_with_meta), str(b)], str(out))
    assert result == str(out)
    assert os.path.isfile(out)

    with fitz.open(out) as d:
        assert d.page_count == 3
        md = d.metadata or {}
        assert md.get("title") == "FirstDoc"
        assert md.get("author") == "UnitTest"


def test_merge_requires_two_inputs(tmp_path):
    a = make_text_pdf(tmp_path / "a.pdf", pages=1)
    with pytest.raises(ValueError):
        merge_pdf.merge_pdfs([str(a)], str(tmp_path / "out.pdf"))


# ---------- Tests: split ----------

def test_split_every(tmp_path):
    src = make_text_pdf(tmp_path / "src.pdf", pages=7)
    outdir = tmp_path / "parts"
    outdir.mkdir()

    parts = splitter.split_pdf(str(src), str(outdir), every=3)
    assert len(parts) == 3

    counts = []
    for p in parts:
        with fitz.open(p) as d:
            counts.append(d.page_count)
    assert counts == [3, 3, 1]


def test_split_at_points(tmp_path):
    src = make_text_pdf(tmp_path / "src.pdf", pages=8)
    outdir = tmp_path / "parts"
    outdir.mkdir()

    parts = splitter.split_pdf(str(src), str(outdir), split_at=[3, 6])
    assert len(parts) == 3

    counts = []
    for p in parts:
        with fitz.open(p) as d:
            counts.append(d.page_count)
    assert counts == [2, 3, 3]


def test_split_invalid_every_raises(tmp_path):
    src = make_text_pdf(tmp_path / "src.pdf", pages=5)
    with pytest.raises(ValueError):
        splitter.split_pdf(str(src), str(tmp_path), every=0)


# ---------- Tests: shrink scanned ----------

def test_shrink_scanned_pdf_basic(tmp_path):
    # Create an image-heavy source PDF which is typically large
    src = make_scanned_like_pdf(tmp_path / "scanned_src.pdf", pages=2, size=(2200, 3000))
    out = tmp_path / "scanned_out.pdf"

    compress_scanned_pdf(str(src), str(out), dpi=120, quality=50, grayscale=False)
    assert os.path.isfile(out)

    with fitz.open(out) as d:
        assert d.page_count == 2
        # Each page should contain at least one image and be JPEG with RGB-ish components
        for i in range(d.page_count):
            page = d.load_page(i)
            imgs = page.get_images(full=True)
            assert len(imgs) >= 1
            xref = imgs[0][0]
            info = d.extract_image(xref)
            assert info.get("ext", "").lower() in ("jpg", "jpeg", "jpe")
            pix = fitz.Pixmap(d, xref)
            try:
                assert pix.n in (3, 4)
            finally:
                pix = None


def test_shrink_grayscale_colorspace(tmp_path):
    src = make_scanned_like_pdf(tmp_path / "scanned_src.pdf", pages=1, size=(1800, 2400))
    out = tmp_path / "scanned_out_gray.pdf"

    compress_scanned_pdf(str(src), str(out), dpi=120, quality=55, grayscale=True)

    with fitz.open(out) as d:
        assert d.page_count == 1
        page = d.load_page(0)
        imgs = page.get_images(full=True)
        assert imgs
        xref = imgs[0][0]
        info = d.extract_image(xref)
        assert info.get("ext", "").lower() in ("jpg", "jpeg", "jpe")
        pix = fitz.Pixmap(d, xref)
        try:
            # 1 or 2 components for grayscale / Gray+alpha
            assert pix.n in (1, 2)
        finally:
            pix = None
