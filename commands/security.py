import base64
import binascii
import hashlib
import html
import secrets
import string

from telegram import Update
from telegram.ext import ContextTypes

from decorators import UserError, handle_errors
from utils import get_args, usage

PASSWORD_DEFAULT = 16
PASSWORD_MIN = 8
PASSWORD_MAX = 128
PASSWORD_GROUPS = (string.ascii_lowercase, string.ascii_uppercase, string.digits, string.punctuation)


@handle_errors("Error al generar la contraseña")
async def password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Genera una contraseña segura con letras, números y símbolos."""
    args: str = get_args(update)
    if args and not args.isdigit():
        raise usage("/password <longitud>")
    length: int = int(args) if args else PASSWORD_DEFAULT
    if not PASSWORD_MIN <= length <= PASSWORD_MAX:
        raise UserError(f"La longitud debe estar entre {PASSWORD_MIN} y {PASSWORD_MAX}")

    # Un carácter de cada grupo como mínimo; el resto, de todos.
    chars: list[str] = [secrets.choice(group) for group in PASSWORD_GROUPS]
    chars += [secrets.choice("".join(PASSWORD_GROUPS)) for _ in range(length - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    await update.effective_message.reply_text(
        f"🔐 Contraseña ({length} caracteres):\n<code>{html.escape(''.join(chars))}</code>"
    )


@handle_errors("Error al generar los hashes")
async def hash_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Genera los hashes MD5, SHA-256 y SHA-512 de un texto."""
    text: str = get_args(update)
    if not text:
        raise usage("/hash <texto>")
    data: bytes = text.encode()
    await update.effective_message.reply_text(
        f"#️⃣ <b>MD5</b>\n<code>{hashlib.md5(data).hexdigest()}</code>\n\n"
        f"<b>SHA-256</b>\n<code>{hashlib.sha256(data).hexdigest()}</code>\n\n"
        f"<b>SHA-512</b>\n<code>{hashlib.sha512(data).hexdigest()}</code>"
    )


@handle_errors("Error al codificar en Base64")
async def base64_encode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Codifica un texto en Base64."""
    text: str = get_args(update)
    if not text:
        raise usage("/base64_encode <texto>")
    await update.effective_message.reply_text(f"<code>{base64.b64encode(text.encode()).decode()}</code>")


@handle_errors("Error al decodificar Base64")
async def base64_decode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Decodifica un texto en Base64."""
    code: str = "".join(get_args(update).split())
    if not code:
        raise usage("/base64_decode <codigo>")
    try:
        decoded: str = base64.b64decode(code + "=" * (-len(code) % 4), validate=True).decode()
    except (binascii.Error, UnicodeDecodeError):
        raise UserError("El código no es Base64 válido o no contiene texto UTF-8") from None
    await update.effective_message.reply_text(f"<code>{html.escape(decoded)}</code>")


@handle_errors("Error al obtener los IDs")
async def show_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Devuelve el ID del usuario y del chat."""
    await update.effective_message.reply_text(
        f"🆔 Usuario: <code>{update.effective_user.id}</code>\n💬 Chat: <code>{update.effective_chat.id}</code>"
    )
