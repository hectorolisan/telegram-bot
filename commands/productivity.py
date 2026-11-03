import html
import re
from datetime import datetime

from telegram import ReplyParameters, Update
from telegram.ext import ContextTypes

from decorators import UserError, handle_errors
from utils import get_args, get_timezone, usage

TIMER_MAX_SECONDS = 24 * 3600
TIMER_UNITS = {"h": 3600, "m": 60, "s": 1, "": 1}
WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def parse_duration(text: str) -> int:
    """Convierte «90», «5m» o «1h30m» en segundos."""
    if not re.fullmatch(r"(\s*\d+\s*[hms]?)+", text, re.IGNORECASE):
        raise usage("/timer <segundos>  (también 5m, 1h30m)")
    return sum(
        int(amount) * TIMER_UNITS[unit.lower()] for amount, unit in re.findall(r"(\d+)\s*([hms]?)", text, re.IGNORECASE)
    )


def format_duration(seconds: int) -> str:
    """Formatea una duración en horas, minutos y segundos."""
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    parts: list[str] = [f"{value} {unit}" for value, unit in ((hours, "h"), (minutes, "min"), (secs, "s")) if value]
    return " ".join(parts) or "0 s"


async def timer_alarm(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Avisa al terminar el temporizador."""
    job = context.job
    await context.bot.send_message(
        chat_id=job.chat_id,
        text=f"⏰ ¡Tiempo! Temporizador de {format_duration(job.data['seconds'])} finalizado",
        reply_parameters=ReplyParameters(message_id=job.data["message_id"], allow_sending_without_reply=True),
    )


@handle_errors("Error al programar el temporizador")
async def timer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Programa un temporizador que avisa al finalizar."""
    args: str = get_args(update)
    if not args:
        raise usage("/timer <segundos>")
    seconds: int = parse_duration(args)
    if not 1 <= seconds <= TIMER_MAX_SECONDS:
        raise UserError("La duración debe estar entre 1 segundo y 24 horas")
    context.job_queue.run_once(
        timer_alarm,
        seconds,
        chat_id=update.effective_chat.id,
        data={"seconds": seconds, "message_id": update.effective_message.message_id},
    )
    await update.effective_message.reply_text(f"⏱️ Temporizador de <b>{format_duration(seconds)}</b> en marcha")


@handle_errors("Error al obtener la hora")
async def now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra la hora, fecha, zona horaria y día del año."""
    current: datetime = datetime.now(get_timezone(get_args(update) or context.user_data.get("timezone")))
    offset: str = current.strftime("%z")
    await update.effective_message.reply_text(
        f"🕒 Hora: <b>{current:%H:%M:%S}</b>\n"
        f"📅 Fecha: {WEEKDAYS[current.weekday()]}, {current.day} de {MONTHS[current.month - 1]} de {current.year}\n"
        f"🌍 Zona horaria: {html.escape(str(current.tzinfo))} ({current.tzname()}, UTC{offset[:3]}:{offset[3:]})\n"
        f"📆 Día del año: {current.timetuple().tm_yday} · Semana ISO: {current.isocalendar().week}"
    )
