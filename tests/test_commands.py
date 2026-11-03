import httpx
import respx

from commands import fun, maths, network, settings, text
from commands.conversion import FRANKFURTER_URL
from tests.conftest import reply


async def test_calculate(make_update):
    update, context = make_update("/calculate 2*(5+3)^2")
    await maths.calculate(update, context)
    assert "<b>128</b>" in reply(update)


async def test_calculate_division_by_zero(make_update):
    update, context = make_update("/calculate 1/0")
    await maths.calculate(update, context)
    assert "División entre cero" in reply(update)


@respx.mock
async def test_translate(make_update):
    respx.get(text.TRANSLATE_URL).mock(
        return_value=httpx.Response(
            200, json={"responseStatus": 200, "responseData": {"translatedText": "hello", "detectedLanguage": "es"}}
        )
    )
    update, context = make_update("/translate en hola")
    await text.translate(update, context)
    assert "es → en" in reply(update)
    assert "hello" in reply(update)


async def test_translate_usage(make_update):
    update, context = make_update("/translate hola")
    await text.translate(update, context)
    assert "Uso:" in reply(update)


@respx.mock
async def test_dns_caps_records(make_update):
    answers = [{"type": 16, "data": f"txt-{i}"} for i in range(network.MAX_DNS_RECORDS + 3)]
    respx.get(network.DNS_URL).mock(return_value=httpx.Response(200, json={"Status": 0, "Answer": answers}))
    update, context = make_update("/dns example.com")
    await network.dns(update, context)
    assert "<b>TXT</b>" in reply(update)
    assert "… y 3 más" in reply(update)


@respx.mock
async def test_dns_nxdomain(make_update):
    respx.get(network.DNS_URL).mock(return_value=httpx.Response(200, json={"Status": 3}))
    update, context = make_update("/dns noexiste.test")
    await network.dns(update, context)
    assert "no existe" in reply(update)


@respx.mock
async def test_ip_lookup_failure(make_update):
    respx.get(url__startswith="http://ip-api.com/json/").mock(
        return_value=httpx.Response(200, json={"status": "fail", "message": "private range"})
    )
    update, context = make_update("/ip 192.168.1.1")
    await network.ip_lookup(update, context)
    assert "private range" in reply(update)


async def test_settz_saves_and_resets(make_update):
    update, context = make_update("/settz Europe/Madrid")
    await settings.settz(update, context)
    assert context.user_data["timezone"] == "Europe/Madrid"

    update, context = make_update("/settz borrar", context.user_data)
    await settings.settz(update, context)
    assert "timezone" not in context.user_data


async def test_settz_rejects_invalid(make_update):
    update, context = make_update("/settz Marte/Olympus")
    await settings.settz(update, context)
    assert "no válida" in reply(update)
    assert "timezone" not in context.user_data


@respx.mock
async def test_setcurrency(make_update, monkeypatch):
    monkeypatch.setattr("commands.conversion.currencies", {})
    respx.get(f"{FRANKFURTER_URL}/currencies").mock(
        return_value=httpx.Response(200, json={"EUR": "Euro", "USD": "United States Dollar"})
    )
    update, context = make_update("/setcurrency €")
    await settings.setcurrency(update, context)
    assert context.user_data["currency"] == "EUR"


@respx.mock
async def test_again_repeats_command(make_update):
    respx.get(fun.QUOTE_URL).mock(return_value=httpx.Response(200, json=[{"q": "Cita", "a": "Autor"}]))
    update, context = make_update("")
    update.callback_query.data = "again:quote"
    await fun.again(update, context)
    assert "Cita" in reply(update)
    assert update.effective_message.reply_text.call_args.kwargs["reply_markup"] is not None


async def test_again_ignores_unknown(make_update):
    update, context = make_update("")
    update.callback_query.data = "again:rm"
    await fun.again(update, context)
    update.effective_message.reply_text.assert_not_called()
