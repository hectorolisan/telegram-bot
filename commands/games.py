import random
import re

from telegram import Update
from telegram.ext import ContextTypes

from decorators import UserError, handle_errors
from utils import get_args, usage

NUMBER_DEFAULT_RANGE = (0, 100)
DIE_DEFAULT_SIDES = 6
DIE_MAX_SIDES = 1000
DIE_FACES = "⚀⚁⚂⚃⚄⚅"


@handle_errors("Error al lanzar la moneda")
async def coin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lanza una moneda al aire."""
    await update.effective_message.reply_text(f"🪙 <b>{random.choice(('Cara', 'Cruz'))}</b>")


@handle_errors("Error al generar el número")
async def number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Genera un número aleatorio en un rango (0-100 por defecto)."""
    args: list[str] = get_args(update).split()
    try:
        values: list[int] = [int(arg) for arg in args]
    except ValueError:
        raise usage("/number <min> <max>") from None
    if len(values) > 2:
        raise usage("/number <min> <max>")
    low, high = (
        NUMBER_DEFAULT_RANGE if not values else (NUMBER_DEFAULT_RANGE[0], values[0]) if len(values) == 1 else values
    )
    low, high = min(low, high), max(low, high)
    await update.effective_message.reply_text(f"🎲 Número entre {low} y {high}: <b>{random.randint(low, high)}</b>")


@handle_errors("Error al lanzar el dado")
async def die(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lanza un dado de 6 caras o de las caras indicadas (/die 20 o /d20)."""
    match = re.match(r"^/d(\d+)", update.effective_message.text or "")
    args: str = match[1] if match else get_args(update)
    if args and not args.isdigit():
        raise usage("/die <caras> o /d<caras>")
    sides: int = int(args) if args else DIE_DEFAULT_SIDES
    if not 2 <= sides <= DIE_MAX_SIDES:
        raise UserError(f"El dado debe tener entre 2 y {DIE_MAX_SIDES} caras")
    result: int = random.randint(1, sides)
    face: str = DIE_FACES[result - 1] if sides == 6 else "🎲"
    await update.effective_message.reply_text(f"{face} Dado de {sides} caras: <b>{result}</b>")
