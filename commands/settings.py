import html

from telegram import Update
from telegram.ext import ContextTypes

from commands.conversion import get_currencies, normalize_currency
from commands.weather import geocode
from decorators import UserError, handle_errors
from utils import get_args, get_timezone

RESET_WORDS = ("-", "borrar", "reset")


async def handle_preference(
    update: Update, context: ContextTypes.DEFAULT_TYPE, key: str, label: str, command: str, example: str
) -> str | None:
    """Muestra o borra la preferencia; devuelve el argumento si hay que guardarlo."""
    value: str = get_args(update)
    if value.lower() in RESET_WORDS:
        context.user_data.pop(key, None)
        await update.effective_message.reply_text(f"🗑️ {label} borrada")
        return None
    if not value:
        saved = context.user_data.get(key)
        current: str = saved["place"] if isinstance(saved, dict) else html.escape(saved or "ninguna")
        await update.effective_message.reply_text(
            f"⚙️ {label} actual: <b>{current}</b>\n\n"
            f"Uso: <code>{command} {example}</code> · <code>{command} borrar</code>"
        )
        return None
    return value


@handle_errors("Error al guardar la zona horaria")
async def settz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guarda la zona horaria por defecto para /now y /ephemeris."""
    name: str | None = await handle_preference(update, context, "timezone", "Zona horaria", "/settz", "Europe/Madrid")
    if name:
        context.user_data["timezone"] = str(get_timezone(name))
        await update.effective_message.reply_text(
            f"✅ Zona horaria guardada: <b>{html.escape(context.user_data['timezone'])}</b>"
        )


@handle_errors("Error al guardar la ciudad")
async def setcity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guarda la ciudad por defecto para /weather."""
    city: str | None = await handle_preference(update, context, "city", "Ciudad", "/setcity", "Madrid")
    if city:
        context.user_data["city"] = await geocode(city)
        await update.effective_message.reply_text(f"✅ Ciudad guardada: <b>{context.user_data['city']['place']}</b>")


@handle_errors("Error al guardar la moneda")
async def setcurrency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guarda la moneda por defecto para /currency y /conversion."""
    query: str | None = await handle_preference(update, context, "currency", "Moneda", "/setcurrency", "EUR")
    if not query:
        return
    code: str = normalize_currency(query)
    supported: dict[str, str] = await get_currencies()
    if code not in supported:
        raise UserError(f"Moneda no soportada: <b>{html.escape(query)}</b>")
    context.user_data["currency"] = code
    await update.effective_message.reply_text(f"✅ Moneda guardada: <b>{html.escape(supported[code])} ({code})</b>")
