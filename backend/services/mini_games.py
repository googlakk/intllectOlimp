"""Deterministic contracts for short textbook-grounded classroom games."""

GROUP_MINI_GAMES = frozenset({"BossRaid", "CodeVault", "KnowledgeAuction", "WordRelay", "PuzzleAssembly"})
INDIVIDUAL_MINI_GAMES = frozenset({"ErrorHunt", "LearningPath"})
MINI_GAME_COMPONENTS = GROUP_MINI_GAMES | INDIVIDUAL_MINI_GAMES


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _fields(value: object, *keys: str) -> bool:
    return isinstance(value, dict) and all(_text(value.get(key)) for key in keys)


def _items(value: object, minimum: int, maximum: int) -> bool:
    return isinstance(value, list) and minimum <= len(value) <= maximum


def _choices(value: object, minimum: int = 2, maximum: int = 4) -> bool:
    return (_items(value, minimum, maximum) and all(_text(item) for item in value)
            and len({item.strip().casefold() for item in value}) == len(value))


def _index(value: object, count: int) -> bool:
    return type(value) is int and 0 <= value < count


def _question(value: object) -> bool:
    return (_fields(value, "question", "explanation") and _choices(value.get("options"))
            and _index(value.get("correct_index"), len(value["options"])))


def _puzzle_problem(content: dict) -> str | None:
    slots, pieces = content.get("slots"), content.get("pieces")
    if not _items(slots, 4, 8) or not _items(pieces, 4, 8) or len(slots) != len(pieces):
        return "нужны 4–8 мест и столько же фрагментов"
    if not all(_fields(slot, "id", "label") for slot in slots) or not all(_fields(piece, "id", "text", "slot_id") for piece in pieces):
        return "укажите id и подпись каждого места, id, текст и место каждого фрагмента"
    slot_ids = {slot["id"] for slot in slots}
    if (len(slot_ids) != len(slots) or len({piece["id"] for piece in pieces}) != len(pieces)
            or {piece["slot_id"] for piece in pieces} != slot_ids):
        return "id должны быть уникальны, каждому месту должен соответствовать ровно один фрагмент"
    return None


def _error_hunt_problem(content: dict) -> str | None:
    lines = content.get("lines")
    if not _items(lines, 3, 6):
        return "нужны 3–6 строк для проверки"
    for line in lines:
        if not _fields(line, "text", "explanation") or type(line.get("is_error")) is not bool:
            return "у каждой строки нужны текст, объяснение и явный признак ошибки"
        if line["is_error"]:
            if not _choices(line.get("fixes")) or not _index(line.get("correct_index"), len(line["fixes"])):
                return "ошибочная строка требует 2–4 разных исправления и индекс правильного"
        elif line.get("fixes") != [] or "correct_index" not in line or line["correct_index"] is not None:
            return "у верной строки fixes должен быть пустым, correct_index — null"
    if {line["is_error"] for line in lines} != {True, False}:
        return "добавьте хотя бы одну верную и одну ошибочную строку"
    return None


def mini_game_problem(component: str, content: object) -> str | None:
    """Reject malformed generated games before preview or publication."""
    if component not in MINI_GAME_COMPONENTS:
        return None
    if not _fields(content, "title", "instruction", "takeaway"):
        return "заполните название, короткие правила и учебный вывод"
    duration = content.get("duration_minutes")
    if type(duration) is not int or not 3 <= duration <= 7:
        return "продолжительность мини-игры должна быть целым числом от 3 до 7 минут"
    if component == "BossRaid":
        rounds = content.get("rounds")
        if not _items(rounds, 3, 5) or not all(_fields(item, "question", "answer", "explanation") for item in rounds):
            return "нужны 3–5 раундов с вопросом, эталонным ответом и объяснением"
    elif component == "CodeVault":
        clues = content.get("clues")
        if not _items(clues, 3, 5) or not all(_fields(item, "label") and _question(item)
                and type(item.get("digit")) is int and 0 <= item["digit"] <= 9 for item in clues):
            return "нужны 3–5 загадок с подписью, 2–4 ответами, правильным индексом, цифрой кода 0–9 и объяснением"
    elif component == "KnowledgeAuction":
        statements = content.get("statements")
        if not _items(statements, 3, 5) or not all(_fields(item, "text", "explanation")
                and type(item.get("is_true")) is bool for item in statements):
            return "нужны 3–5 утверждений с признаком истинности и объяснением"
        if {item["is_true"] for item in statements} != {True, False}:
            return "на аукционе должны быть и верные, и ложные утверждения"
    elif component == "WordRelay":
        cards = content.get("cards")
        if not _items(cards, 4, 8):
            return "нужны 4–8 понятий для объяснения"
        for card in cards:
            if not _fields(card, "term", "hint") or not _choices(card.get("forbidden"), 3, 5):
                return "у понятия нужны подсказка и 3–5 разных запрещённых слов"
            if card["term"].strip().casefold() in {word.strip().casefold() for word in card["forbidden"]}:
                return "запрещённые слова не должны повторять само понятие"
    elif component == "PuzzleAssembly":
        return _puzzle_problem(content)
    elif component == "ErrorHunt":
        return _error_hunt_problem(content)
    elif component == "LearningPath":
        checkpoints = content.get("checkpoints")
        if not _items(checkpoints, 3, 3) or not all(_fields(item, "label")
                and _question(item.get("support")) and _question(item.get("challenge")) for item in checkpoints):
            return "нужны ровно 3 этапа, у каждого название и два задания с 2–4 ответами и объяснением"
    return None
