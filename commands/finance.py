import asyncio
import html
from datetime import date, timedelta

from telegram import Update
from telegram.ext import ContextTypes

from commands.conversion import FRANKFURTER_URL, get_currencies, normalize_currency
from decorators import UserError, handle_errors
from utils import fetch_json, format_number, get_args, usage

COINGECKO_URL = "https://api.coingecko.com/api/v3"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}
CURRENCY_QUOTES = ("EUR", "USD", "GBP", "JPY", "CHF")
MARKET_INDICES = {"^IBEX": "IBEX 35", "^GSPC": "S&amp;P 500", "^IXIC": "Nasdaq", "^DJI": "Dow Jones"}
CACHE_TTL = 120
MARKET_CRYPTOS = {"bitcoin": "BTC", "ethereum": "ETH", "binancecoin": "BNB", "solana": "SOL", "dogecoin": "DOGE"}


def format_change(change: float | None) -> str:
    """Formatea una variación porcentual con su indicador."""
    if change is None:
        return "N/D"
    return f"{'🟢' if change >= 0 else '🔴'} {'+' if change >= 0 else ''}{format_number(change)} %"


def format_price(price: float) -> str:
    """Formatea un precio con más decimales si es pequeño."""
    return format_number(price, 2 if price >= 1 else 6)


def format_compact(value: float) -> str:
    """Formatea cantidades grandes en miles de millones o millones."""
    for divisor, suffix in ((1e12, "B"), (1e9, "mil M"), (1e6, "M")):
        if value >= divisor:
            return f"{format_number(value / divisor)} {suffix}"
    return format_number(value)


@handle_errors("Error al consultar la criptomoneda")
async def crypto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra precio, variación 24h y volumen de una criptomoneda."""
    query: str = get_args(update)
    if not query:
        raise usage("/crypto <simbolo>")
    coins: list[dict] = (await fetch_json(f"{COINGECKO_URL}/search", params={"query": query}, ttl=CACHE_TTL))["coins"]
    coin: dict | None = next(
        (c for c in coins if query.lower() in (c["symbol"].lower(), c["id"], c["name"].lower())),
        coins[0] if coins else None,
    )
    if not coin:
        raise UserError(f"No se encontró la criptomoneda <b>{html.escape(query)}</b>")

    data: dict = (
        await fetch_json(
            f"{COINGECKO_URL}/simple/price",
            params={
                "ids": coin["id"],
                "vs_currencies": "usd,eur",
                "include_24hr_change": "true",
                "include_24hr_vol": "true",
                "include_market_cap": "true",
            },
            ttl=CACHE_TTL,
        )
    )[coin["id"]]
    await update.effective_message.reply_text(
        f"🪙 <b>{html.escape(coin['name'])} ({html.escape(coin['symbol'].upper())})</b>\n\n"
        f"💵 Precio: {format_price(data['usd'])} $ · {format_price(data['eur'])} €\n"
        f"📈 Variación 24h: {format_change(data.get('usd_24h_change'))}\n"
        f"📊 Volumen 24h: {format_compact(data.get('usd_24h_vol', 0))} $\n"
        f"🏦 Capitalización: {format_compact(data.get('usd_market_cap', 0))} $"
    )


@handle_errors("Error al consultar la moneda")
async def currency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra el cambio actual y la variación diaria de una divisa."""
    query: str = get_args(update) or context.user_data.get("currency", "")
    if not query:
        raise usage("/currency <simbolo>")
    code: str = normalize_currency(query)
    supported: dict[str, str] = await get_currencies()
    if code not in supported:
        raise UserError(f"Moneda no soportada: <b>{html.escape(query)}</b>")

    quotes: list[str] = [quote for quote in CURRENCY_QUOTES if quote != code]
    start: str = (date.today() - timedelta(days=7)).isoformat()
    data: dict = await fetch_json(
        f"{FRANKFURTER_URL}/{start}..", params={"base": code, "symbols": ",".join(quotes)}, ttl=CACHE_TTL
    )
    days: list[str] = sorted(data["rates"])
    latest, previous = data["rates"][days[-1]], data["rates"][days[-2]]

    lines: list[str] = [
        f"• 1 {code} = <b>{format_number(latest[quote], 4)} {quote}</b>  "
        f"{format_change((latest[quote] / previous[quote] - 1) * 100)}"
        for quote in quotes
    ]
    await update.effective_message.reply_text(
        f"💱 <b>{html.escape(supported[code])} ({code})</b>\n\n"
        + "\n".join(lines)
        + f"\n\n📅 BCE {days[-1]} (variación frente a {days[-2]})\n"
        "📊 Volumen: N/D (las divisas no tienen un volumen público centralizado)"
    )


async def fetch_index(symbol: str) -> tuple[float, float | None]:
    """Obtiene el precio y la variación diaria de un índice bursátil."""
    data: dict = await fetch_json(
        YAHOO_CHART_URL.format(symbol=symbol),
        params={"range": "1d", "interval": "1d"},
        headers=YAHOO_HEADERS,
        ttl=CACHE_TTL,
    )
    meta: dict = data["chart"]["result"][0]["meta"]
    price: float = meta["regularMarketPrice"]
    change: float | None = meta.get("regularMarketChangePercent")
    if change is None and meta.get("chartPreviousClose"):
        change = (price / meta["chartPreviousClose"] - 1) * 100
    return price, change


@handle_errors("Error al consultar los mercados")
async def financial_market(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resume el estado de los principales índices y criptomonedas."""
    indices, cryptos = await asyncio.gather(
        asyncio.gather(*(fetch_index(symbol) for symbol in MARKET_INDICES), return_exceptions=True),
        fetch_json(
            f"{COINGECKO_URL}/simple/price",
            params={
                "ids": ",".join(MARKET_CRYPTOS),
                "vs_currencies": "usd",
                "include_24hr_change": "true",
            },
            ttl=CACHE_TTL,
        ),
    )
    index_lines: list[str] = [
        f"• {name}: N/D"
        if isinstance(result, Exception)
        else f"• {name}: <b>{format_number(result[0])}</b>  {format_change(result[1])}"
        for name, result in zip(MARKET_INDICES.values(), indices, strict=True)
    ]
    crypto_lines: list[str] = [
        f"• {symbol}: <b>{format_price(cryptos[coin_id]['usd'])} $</b>  "
        f"{format_change(cryptos[coin_id].get('usd_24h_change'))}"
        for coin_id, symbol in MARKET_CRYPTOS.items()
        if coin_id in cryptos
    ]
    await update.effective_message.reply_text(
        "📈 <b>Índices</b>\n" + "\n".join(index_lines) + "\n\n🪙 <b>Criptomonedas (24h)</b>\n" + "\n".join(crypto_lines)
    )
