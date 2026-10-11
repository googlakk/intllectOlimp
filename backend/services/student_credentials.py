"""Short student credentials and strict validation of manual temporary passwords."""

import secrets

from services.auth import AuthServiceError

LOWER = "abcdefghjkmnpqrstuvwxyz"
UPPER = "ABCDEFGHJKMNPQRSTUVWXYZ"
DIGITS = "23456789"


def student_temporary_password() -> str:
    characters = [secrets.choice(LOWER), secrets.choice(UPPER), secrets.choice(DIGITS)]
    characters.extend(secrets.choice(LOWER + UPPER + DIGITS) for _ in range(5))
    secrets.SystemRandom().shuffle(characters)
    return "".join(characters)


def validate_temporary_password(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not 6 <= len(value) <= 128 or any(character.isspace() for character in value):
        raise AuthServiceError(422, "Временный пароль: от 6 до 128 символов без пробелов.")
    return value


def generated_student_login(organization_id: int, classroom_id: int) -> str:
    suffix = "".join(secrets.choice(LOWER + DIGITS) for _ in range(6))
    return f"s{organization_id}c{classroom_id}-{suffix}"
