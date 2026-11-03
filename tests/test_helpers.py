import httpx
import pytest
import respx

from commands.conversion import convert_unit, normalize_currency
from commands.maths import is_prime
from commands.productivity import format_duration, parse_duration
from decorators import UserError
from utils import extract_host, fetch_json, format_number, parse_number, truncate


def test_parse_number_accepts_comma():
    assert parse_number("1,5") == 1.5
    with pytest.raises(UserError):
        parse_number("abc")


def test_format_number_spanish_separators():
    assert format_number(1234567.891) == "1.234.567,89"


def test_truncate():
    assert truncate("hola", 10) == "hola"
    assert truncate("hola mundo", 5) == "hola…"


def test_extract_host():
    assert extract_host("https://example.com/path") == "example.com"
    assert extract_host("example.com") == "example.com"


@pytest.mark.parametrize(("text", "seconds"), [("90", 90), ("5m", 300), ("1h30m", 5400), ("1h 2m 3s", 3723)])
def test_parse_duration(text, seconds):
    assert parse_duration(text) == seconds


def test_parse_duration_rejects_garbage():
    with pytest.raises(UserError):
        parse_duration("diez")


def test_format_duration():
    assert format_duration(3723) == "1 h 2 min 3 s"
    assert format_duration(0) == "0 s"


def test_is_prime():
    assert [n for n in range(20) if is_prime(n)] == [2, 3, 5, 7, 11, 13, 17, 19]
    assert is_prime(2**61 - 1)


def test_normalize_currency():
    assert normalize_currency("€") == "EUR"
    assert normalize_currency("usd") == "USD"


def test_convert_unit():
    assert "<b>1 km</b>" in convert_unit(1000, "metros", "km")
    with pytest.raises(UserError):
        convert_unit(1, "km", "kg")


@respx.mock
async def test_fetch_json_cache():
    route = respx.get("https://api.test/data").mock(return_value=httpx.Response(200, json={"v": 1}))
    assert await fetch_json("https://api.test/data", ttl=60) == {"v": 1}
    assert await fetch_json("https://api.test/data", ttl=60) == {"v": 1}
    assert route.call_count == 1
    await fetch_json("https://api.test/data")
    assert route.call_count == 2
