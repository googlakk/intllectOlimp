"""Application use case for parsing uploaded KTP files into editable drafts."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from errors import ApplicationError

from .extract import Extraction, extract
from .mapper import map_to_schema
from services.curriculum_graph import enrich_ktp_draft

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_SUFFIXES = (".xlsx", ".docx", ".pdf")

Extractor = Callable[[bytes, str], Extraction]
Mapper = Callable[[Extraction], Awaitable[dict[str, Any]]]


class KtpParseError(ApplicationError):
    pass


def validate_upload(filename: str, data: bytes) -> None:
    if not filename.lower().endswith(ALLOWED_SUFFIXES):
        raise KtpParseError(
            status_code=422,
            detail="Поддерживаются файлы .xlsx, .docx и .pdf",
        )
    if not data:
        raise KtpParseError(status_code=422, detail="Файл пустой")
    if len(data) > MAX_UPLOAD_BYTES:
        raise KtpParseError(
            status_code=413,
            detail=f"Файл больше {MAX_UPLOAD_BYTES // (1024 * 1024)} МБ",
        )


def attach_parse_metadata(
    draft: dict[str, Any],
    *,
    filename: str,
    extraction: Extraction,
) -> dict[str, Any]:
    topics = [
        topic
        for section in draft.get("sections") or []
        for topic in (section.get("topics") or [])
    ]
    draft["source"] = {
        "filename": filename,
        "kind": extraction.source_kind,
        "table_count": len(extraction.tables),
        "row_count": extraction.row_count,
    }
    draft["stats"] = {
        "section_count": len(draft.get("sections") or []),
        "topic_count": len(topics),
        "low_confidence_count": sum(1 for topic in topics if topic.get("confidence") == "low"),
        "with_objectives": sum(
            1
            for topic in topics
            if (topic.get("learning_objectives") or "").strip()
            and topic.get("objective_source") != "inferred"
        ),
    }
    return draft


async def parse_ktp_draft(
    *,
    filename: str,
    data: bytes,
    extractor: Extractor = extract,
    mapper: Mapper = map_to_schema,
) -> dict[str, Any]:
    validate_upload(filename, data)

    try:
        extraction = extractor(data, filename)
    except Exception as exc:
        raise KtpParseError(status_code=422, detail=f"Не удалось прочитать файл: {exc}") from exc

    if not extraction.tables:
        raise KtpParseError(
            status_code=422,
            detail=(
                "В файле не найдено таблиц. Убедитесь, что КТП оформлен таблицей, "
                "а не картинкой или сканом."
            ),
        )

    try:
        draft = await mapper(extraction)
    except RuntimeError as exc:
        raise KtpParseError(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise KtpParseError(status_code=502, detail=f"Сбой разбора: {exc}") from exc

    draft = enrich_ktp_draft(draft)
    return attach_parse_metadata(draft, filename=filename, extraction=extraction)
