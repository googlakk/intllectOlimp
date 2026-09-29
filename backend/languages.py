"""Языки обучения: предмет ведётся на одном языке, и его уроки строятся по учебникам этого же языка."""

from typing import Literal

Language = Literal["ru", "ky", "en"]
LANGUAGES: tuple[str, ...] = ("ru", "ky", "en")
# «Урок на … языке»: предложный падеж для промпта генератора.
LANGUAGE_PROMPT_LABEL = {"ru": "русском", "ky": "кыргызском", "en": "английском"}
LANGUAGE_NAME = {"ru": "русский", "ky": "кыргызский", "en": "английский"}


def normalize_language(value: object) -> str:
    return value if isinstance(value, str) and value in LANGUAGES else "ru"
