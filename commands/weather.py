import html

from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from decorators import UserError, handle_errors
from utils import fetch_json, get_args

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CURRENT_FIELDS = (
    "temperature_2m,relative_humidity_2m,dew_point_2m,apparent_temperature,"
    "precipitation_probability,weather_code,wind_speed_10m"
)
WMO_CODES = {
    0: "☀️ Despejado",
    1: "🌤️ Mayormente despejado",
    2: "⛅ Parcialmente nublado",
    3: "☁️ Nublado",
    45: "🌫️ Niebla",
    48: "🌫️ Niebla con escarcha",
    51: "🌦️ Llovizna ligera",
    53: "🌦️ Llovizna moderada",
    55: "🌦️ Llovizna intensa",
    56: "🌧️ Llovizna helada ligera",
    57: "🌧️ Llovizna helada intensa",
    61: "🌧️ Lluvia ligera",
    63: "🌧️ Lluvia moderada",
    65: "🌧️ Lluvia intensa",
    66: "🌧️ Lluvia helada ligera",
    67: "🌧️ Lluvia helada intensa",
    71: "🌨️ Nevada ligera",
    73: "🌨️ Nevada moderada",
    75: "❄️ Nevada intensa",
    77: "🌨️ Granos de nieve",
    80: "🌦️ Chubascos ligeros",
    81: "🌧️ Chubascos moderados",
    82: "⛈️ Chubascos violentos",
    85: "🌨️ Chubascos de nieve ligeros",
    86: "❄️ Chubascos de nieve intensos",
    95: "⛈️ Tormenta",
    96: "⛈️ Tormenta con granizo ligero",
    99: "⛈️ Tormenta con granizo fuerte",
}


async def get_weather_text(latitude: float, longitude: float, place: str) -> str:
    """Consulta Open-Meteo y formatea el tiempo actual."""
    data: dict = await fetch_json(
        FORECAST_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": CURRENT_FIELDS,
            "timezone": "auto",
        },
    )
    current: dict = data["current"]
    return (
        f"⛅ <b>Tiempo en {place}</b>\n"
        f"{WMO_CODES.get(current['weather_code'], '❔ Desconocido')}\n\n"
        f"🌡️ Temperatura: {current['temperature_2m']} °C\n"
        f"🤗 Sensación térmica: {current['apparent_temperature']} °C\n"
        f"💧 Humedad relativa: {current['relative_humidity_2m']} %\n"
        f"💦 Punto de rocío: {current['dew_point_2m']} °C\n"
        f"☔ Probabilidad de lluvia: {current['precipitation_probability']} %\n"
        f"💨 Viento: {current['wind_speed_10m']} km/h"
    )


@handle_errors("Error al consultar el tiempo")
async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra el tiempo de una ciudad o pide la ubicación."""
    city: str = get_args(update)
    if not city:
        if update.effective_chat.type != ChatType.PRIVATE:
            raise UserError("Indiquen una ciudad: <code>/weather Madrid</code>")
        await update.effective_message.reply_text(
            "📍 Compartan su ubicación para consultar el tiempo:",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("📍 Enviar ubicación", request_location=True)]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
        return

    data: dict = await fetch_json(GEOCODING_URL, params={"name": city, "count": 1, "language": "es"})
    if not data.get("results"):
        raise UserError(f"No se encontró la ciudad <b>{html.escape(city)}</b>")
    result: dict = data["results"][0]
    place: str = html.escape(", ".join(filter(None, [result["name"], result.get("admin1"), result.get("country")])))
    await update.effective_message.reply_text(await get_weather_text(result["latitude"], result["longitude"], place))


@handle_errors("Error al consultar el tiempo")
async def weather_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra el tiempo de la ubicación compartida."""
    location = update.effective_message.location
    place: str = f"su ubicación ({location.latitude:.3f}, {location.longitude:.3f})"
    await update.effective_message.reply_text(
        await get_weather_text(location.latitude, location.longitude, place), reply_markup=ReplyKeyboardRemove()
    )
