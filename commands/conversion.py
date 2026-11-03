import html
import re

from pint import DimensionalityError, UndefinedUnitError, UnitRegistry
from telegram import Update
from telegram.ext import ContextTypes

from decorators import UserError, handle_errors
from utils import fetch_json, format_number, get_args, parse_number, usage

FRANKFURTER_URL = "https://api.frankfurter.dev/v1"
CURRENCY_ALIASES = {
    "€": "EUR", "euro": "EUR", "euros": "EUR",
    "$": "USD", "dolar": "USD", "dólar": "USD", "dolares": "USD", "dólares": "USD",
    "£": "GBP", "libra": "GBP", "libras": "GBP",
    "¥": "JPY", "yen": "JPY", "yenes": "JPY",
    "franco": "CHF", "francos": "CHF", "yuan": "CNY", "yuanes": "CNY",
    "real": "BRL", "reales": "BRL", "rupia": "INR", "rupias": "INR",
    "peso": "MXN", "pesos": "MXN",
}
UNIT_ALIASES = {
    "c": "degC", "°c": "degC", "ºc": "degC", "celsius": "degC",
    "f": "degF", "°f": "degF", "ºf": "degF", "fahrenheit": "degF",
    "k": "kelvin",
}
for singular, plural, unit in [
    ("segundo", "segundos", "second"), ("seg", "segs", "second"), ("minuto", "minutos", "minute"),
    ("hora", "horas", "hour"), ("dia", "dias", "day"), ("día", "días", "day"),
    ("semana", "semanas", "week"), ("mes", "meses", "month"), ("año", "años", "year"),
    ("metro", "metros", "meter"), ("kilometro", "kilometros", "kilometer"),
    ("kilómetro", "kilómetros", "kilometer"), ("centimetro", "centimetros", "centimeter"),
    ("centímetro", "centímetros", "centimeter"), ("milimetro", "milimetros", "millimeter"),
    ("milímetro", "milímetros", "millimeter"), ("milla", "millas", "mile"), ("pie", "pies", "foot"),
    ("pulgada", "pulgadas", "inch"), ("yarda", "yardas", "yard"), ("gramo", "gramos", "gram"),
    ("kilo", "kilos", "kilogram"), ("kilogramo", "kilogramos", "kilogram"), ("onza", "onzas", "ounce"),
    ("tonelada", "toneladas", "metric_ton"), ("litro", "litros", "liter"),
    ("mililitro", "mililitros", "milliliter"), ("galon", "galones", "gallon"), ("galón", "galones", "gallon"),
]:
    UNIT_ALIASES[singular] = UNIT_ALIASES[plural] = unit

ureg = UnitRegistry()
currencies: dict[str, str] = {}


def normalize_currency(value: str) -> str:
    """Convierte símbolos y nombres de moneda a su código ISO."""
    return CURRENCY_ALIASES.get(value.lower(), value.upper())


async def get_currencies() -> dict[str, str]:
    """Devuelve las divisas soportadas (con caché en memoria)."""
    if not currencies:
        currencies.update(await fetch_json(f"{FRANKFURTER_URL}/currencies"))
    return currencies


async def convert_currency(amount: float, source: str, target: str) -> str:
    """Convierte divisas con los tipos de cambio del BCE."""
    if source == target:
        return f"{format_number(amount)} {source} = {format_number(amount)} {target}"
    data: dict = await fetch_json(
        f"{FRANKFURTER_URL}/latest", params={"base": source, "symbols": target}
    )
    rate: float = data["rates"][target]
    return (
        f"💱 {format_number(amount)} {source} = <b>{format_number(amount * rate)} {target}</b>\n"
        f"1 {source} = {format_number(rate, 4)} {target} · {data['date']}"
    )


def convert_unit(amount: float, source: str, target: str) -> str:
    """Convierte unidades físicas (longitud, masa, tiempo, temperatura...)."""
    source_unit: str = UNIT_ALIASES.get(source.lower(), source)
    target_unit: str = UNIT_ALIASES.get(target.lower(), target)
    try:
        result = ureg.Quantity(amount, source_unit).to(target_unit)
    except UndefinedUnitError as e:
        raise UserError(f"Unidad desconocida: <code>{html.escape(', '.join(e.unit_names))}</code>")
    except DimensionalityError:
        raise UserError(
            f"No se puede convertir <code>{html.escape(source)}</code> a <code>{html.escape(target)}</code>"
        )
    value: str = format_number(result.magnitude, 6).rstrip("0").rstrip(",")
    return f"🔄 {format_number(amount, 6).rstrip('0').rstrip(',')} {html.escape(source)} = <b>{value} {html.escape(target)}</b>"


@handle_errors("Error al realizar la conversión")
async def conversion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Conversor universal de divisas y unidades."""
    match = re.fullmatch(r"(\S+)\s+(\S+)\s+(?:(?:a|to|en|->)\s+)?(\S+)", get_args(update), re.IGNORECASE)
    if not match:
        raise usage("/conversion <cantidad> <origen> <destino>")
    amount: float = parse_number(match[1])
    source, target = match[2], match[3]

    source_currency, target_currency = normalize_currency(source), normalize_currency(target)
    supported: dict[str, str] = await get_currencies()
    if source_currency in supported and target_currency in supported:
        text: str = await convert_currency(amount, source_currency, target_currency)
    else:
        text = convert_unit(amount, source, target)
    await update.effective_message.reply_text(text)
