"""HTTP-клиент: httpx или httpx2 — что установлено.

Пакет anthropic в разных версиях тянет за собой разные имена одной и той же
библиотеки: старые — httpx, начиная с 1.7 — httpx2. API у них совпадает в той
части, которую использует шлюз (AsyncClient, Response, MockTransport,
HTTPError, Timeout), поэтому берём тот, что есть, и не добавляем лишнюю
зависимость.

Почему это отдельный файл: жёсткий `import httpx` уже сломал прогон тестов на
рабочей машине, хотя в среде разработки всё было зелено. Различие сред должно
обрабатываться в одном месте, а не всплывать в каждом импорте.
"""

from __future__ import annotations

try:                    # httpx2 — то, что ставит свежий anthropic
    import httpx2 as httpx
    HTTP_LIBRARY = "httpx2"
except ImportError:     # pragma: no cover — путь для старых окружений
    try:
        import httpx
        HTTP_LIBRARY = "httpx"
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Не найдена библиотека HTTP: ни httpx2, ни httpx. "
            "Установите зависимости: pip install -r requirements.txt"
        ) from exc

AsyncClient = httpx.AsyncClient
Response = httpx.Response
HTTPError = httpx.HTTPError
Timeout = httpx.Timeout
MockTransport = httpx.MockTransport

__all__ = [
    "httpx", "HTTP_LIBRARY", "AsyncClient", "Response",
    "HTTPError", "Timeout", "MockTransport",
]
