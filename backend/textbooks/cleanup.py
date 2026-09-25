"""Очистка текста страниц учебника. Только безопасные правки: смысл не меняется."""

from __future__ import annotations

import re

# Кириллица в кодировке cp1251, прочитанная как latin-1 («Êûðãûçñêèå» вместо «Кыргызские»).
_MOJIBAKE = re.compile(r"[À-ÿ¨¸]")
# Вместе с буквами перекодируются и остальные байты 0x80–0xFF (¹ → №, ³ → і).
_HIGH_BYTE = re.compile(r"[\x80-\xff]")
MOJIBAKE_SHARE = 0.3

# Служебный мусор шрифтов: (cid:17), /g44/g3.
_GLYPH_GARBAGE = re.compile(r"\(cid:\d+\)|(?:/g\d+)+")

# Водяные знаки сайтов, в том числе с задвоенными буквами («wwwwww..bbiizzddiinn..kkgg»).
_WATERMARKS = (
    re.compile(r"w{3,}\.+b+i+z+d+i+n+\.+k+g+", re.IGNORECASE),
    re.compile(r"Скачан[оа]? с\s+(?:сайта\s+)?\S+", re.IGNORECASE),
    re.compile(r"(?:https?://)?vk\.com/\S+", re.IGNORECASE),
)

# Латинские буквы, похожие на кириллические, внутри русских слов («arpeccии» → «агрессии»).
_LOOKALIKES = str.maketrans("aeopcxyAEOPCXHKMTBr", "аеорсхуАЕОРСХНКМТВг")
_CYRILLIC = re.compile(r"[А-Яа-яЁё]")
_MIXED_WORD = re.compile(r"\b(?=\w*[А-Яа-яЁё])(?=\w*[A-Za-z])\w+\b")
# Обозначение с русским индексом («pатм», «Eк», «Tпл»): латинская буква и до 4 кириллических — не слово.
_SUBSCRIPT = re.compile(r"^[A-Za-z][А-Яа-яЁё]{1,4}$")
LOOKALIKE_MIN_LEN = 4

_SOFT_HYPHEN = "\u00ad"
# Перенос: «форми-\nруется» → «формируется» (только если дальше строчная буква).
_HYPHEN_BREAK = re.compile(r"(\w+)[-\u2010\u00ad]\n([a-zа-яё]+)")
# Настоящий дефис на конце строки: «северо-запад», «из-за», «кто-то», «по-русски».
_HYPHEN_PREFIXES = ("северо", "юго", "из", "по", "кое", "во", "в", "общественно", "научно", "социально",
                    "культурно", "военно", "физико", "химико", "историко", "экономико")
_HYPHEN_PARTICLES = ("то", "либо", "нибудь", "ка", "таки", "за", "под")


def fix_mojibake(text: str) -> str:
    letters = [char for char in text if char.isalpha()]
    if not letters or sum(bool(_MOJIBAKE.match(char)) for char in letters) / len(letters) < MOJIBAKE_SHARE:
        return text
    return "".join(_cp1251(char) if _HIGH_BYTE.match(char) else char for char in text)


def _cp1251(char: str) -> str:
    try:
        return bytes([ord(char)]).decode("cp1251")
    except UnicodeDecodeError:  # 0x98 в cp1251 не определён
        return char


_MATH = re.compile(r"(\$[^$]*\$)")


def fix_lookalikes(text: str) -> str:
    """Формулы в $…$ не трогаем: там «pатм» — обозначение, а не опечатка."""
    return "".join(
        part if part.startswith("$") else _MIXED_WORD.sub(lambda match: _fix_word(match.group(0)), part)
        for part in _MATH.split(text)
    )


def _fix_word(word: str) -> str:
    if len(word) < LOOKALIKE_MIN_LEN or _SUBSCRIPT.match(word):
        return word
    return word.translate(_LOOKALIKES)


def remove_watermarks(text: str) -> str:
    for pattern in _WATERMARKS:
        text = pattern.sub("", text)
    return text


def join_hyphenation(text: str) -> str:
    def join(match: re.Match[str]) -> str:
        left, right = match.group(1), match.group(2)
        if left.casefold() in _HYPHEN_PREFIXES or right.casefold() in _HYPHEN_PARTICLES:
            return f"{left}-{right}"
        return left + right

    return _HYPHEN_BREAK.sub(join, text).replace(_SOFT_HYPHEN, "")


def clean_page_text(text: str) -> str:
    text = fix_mojibake(text)
    text = _GLYPH_GARBAGE.sub("", text)
    text = remove_watermarks(text)
    text = fix_lookalikes(text)
    text = join_hyphenation(text)
    lines = [re.sub(r"[ \t]{2,}", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)
