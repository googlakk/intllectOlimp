"""Helpers for creating user accounts (login generation)."""
import re

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "ң": "n", "о": "o", "ө": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ү": "u", "ф": "f", "х": "kh", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def transliterate(text: str) -> str:
    return "".join(_TRANSLIT.get(char, char) for char in text.casefold())


def base_login(full_name: str) -> str:
    """'Айбек Исаков' -> 'aibek.isakov' style base (first two name parts)."""
    parts = [re.sub(r"[^a-z0-9]", "", transliterate(part)) for part in full_name.split()]
    parts = [part for part in parts if part]
    return ".".join(parts[:2]) or "user"


def unique_login(full_name: str, taken: set[str]) -> str:
    return numbered_login(base_login(full_name), taken)


def numbered_login(base: str, taken: set[str]) -> str:
    """base, base2, base3... — first one not in `taken` (which is updated)."""
    login, counter = base, 2
    while login in taken:
        login, counter = f"{base}{counter}", counter + 1
    taken.add(login)
    return login
