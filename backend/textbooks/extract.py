"""Страницы PDF: текстовый слой или скан.

Текстовый слой берётся только в границах страницы и без задвоенных символов:
в части учебников (география) слой содержит текст соседней страницы за краем
и символы, нарисованные дважды «для жирности».
"""

from __future__ import annotations

import io
from dataclasses import dataclass

# Меньше символов на странице с картинкой — это скан (или почти пустая страница).
SCAN_MIN_CHARS = 50
RENDER_DPI = 170
RENDER_MAX_SIDE = 1800


@dataclass(frozen=True)
class PageText:
    index: int          # номер страницы в PDF, с нуля
    text: str
    is_scan: bool


def page_is_scan(text: str, has_images: bool) -> bool:
    return has_images and len(text.strip()) < SCAN_MIN_CHARS


def extract_pages(data: bytes, *, start: int = 0, end: int | None = None) -> list[PageText]:
    import pdfplumber

    pages: list[PageText] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for index in range(start, min(end if end is not None else len(pdf.pages), len(pdf.pages))):
            page = pdf.pages[index]
            width, height = page.width, page.height
            inside = page.filter(
                lambda obj, w=width, h=height: obj.get("object_type") != "char"
                or (obj.get("x0", 0) >= -1 and obj.get("x1", 0) <= w + 1
                    and obj.get("top", 0) >= -1 and obj.get("bottom", 0) <= h + 1)
            ).dedupe_chars()
            text = inside.extract_text() or ""
            pages.append(PageText(index=index, text=text, is_scan=page_is_scan(text, bool(page.images))))
            page.close()  # pdfplumber кэширует разобранные страницы — без этого память растёт с каждой
    return pages


def page_count(data: bytes) -> int:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return len(pdf.pages)


def render_scale(width_pt: float, height_pt: float, *, dpi: int = RENDER_DPI, max_side: int = RENDER_MAX_SIDE) -> float:
    """Масштаб считается ДО рендера: огромная страница (до 14400 pt) иначе займёт гигабайты памяти."""
    longest = max(width_pt, height_pt, 1.0)
    return min(dpi / 72, max_side / longest)


def render_pages_png(data: bytes, indices: list[int], *, dpi: int = RENDER_DPI, max_side: int = RENDER_MAX_SIDE):
    """Страницы картинками для распознавания; документ открывается один раз."""
    import pypdfium2

    document = pypdfium2.PdfDocument(data)
    try:
        for index in indices:
            page = document[index]
            try:
                width, height = page.get_size()
                image = page.render(scale=render_scale(width, height, dpi=dpi, max_side=max_side)).to_pil()
            finally:
                page.close()
            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, format="PNG", optimize=True)
            yield index, buffer.getvalue()
    finally:
        document.close()
