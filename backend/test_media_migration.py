import base64

import pytest

from services.media_migration import parse_data_url


def test_parse_data_url_decodes_payload():
    mime, raw = parse_data_url("data:image/png;base64," + base64.b64encode(b"png").decode())
    assert mime == "image/png"
    assert raw == b"png"


def test_parse_data_url_rejects_remote_url():
    with pytest.raises(ValueError):
        parse_data_url("https://example.com/image.png")
