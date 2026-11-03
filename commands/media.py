import colorsys
import hashlib
import random
from io import BytesIO

import qrcode
from PIL import Image, ImageDraw, ImageFont
from telegram import Update
from telegram.ext import ContextTypes

from decorators import UserError, handle_errors
from utils import get_args, usage

QR_MAX_LENGTH = 1000
SWATCH_SIZE = (600, 300)
AVATAR_GRID = 5
AVATAR_CELL = 70
AVATAR_MARGIN = 35
AVATAR_BACKGROUND = "#F0F0F0"


def to_png(image: Image.Image) -> BytesIO:
    """Guarda una imagen en memoria como PNG."""
    buffer: BytesIO = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convierte un color hexadecimal a RGB."""
    return tuple(int(hex_color[i : i + 2], 16) for i in (1, 3, 5))


def text_color(hex_color: str) -> str:
    """Elige texto blanco o negro según la luminancia del fondo."""
    r, g, b = hex_to_rgb(hex_color)
    return "#000000" if 0.299 * r + 0.587 * g + 0.114 * b > 150 else "#FFFFFF"


def hls_to_hex(hue: float, lightness: float, saturation: float) -> str:
    """Convierte un color HLS a hexadecimal."""
    r, g, b = colorsys.hls_to_rgb(hue % 1, lightness, saturation)
    return f"#{round(r * 255):02X}{round(g * 255):02X}{round(b * 255):02X}"


def draw_swatches(colors: list[str]) -> Image.Image:
    """Dibuja franjas de color con su código hexadecimal."""
    width, height = SWATCH_SIZE
    image: Image.Image = Image.new("RGB", SWATCH_SIZE)
    draw: ImageDraw.ImageDraw = ImageDraw.Draw(image)
    font: ImageFont.FreeTypeFont = ImageFont.load_default(size=36 if len(colors) == 1 else 22)
    stripe: float = width / len(colors)
    for index, color in enumerate(colors):
        box: tuple[float, ...] = (index * stripe, 0, (index + 1) * stripe, height)
        draw.rectangle(box, fill=color)
        draw.text(((box[0] + box[2]) / 2, height - 30), color, fill=text_color(color), font=font, anchor="ms")
    return image


@handle_errors("Error al generar el código QR")
async def qr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Genera un código QR a partir de un texto o URL."""
    text: str = get_args(update)
    if not text:
        raise usage("/qr <texto_o_url>")
    if len(text) > QR_MAX_LENGTH:
        raise UserError(f"El texto no puede superar {QR_MAX_LENGTH} caracteres")
    image: Image.Image = qrcode.make(text, box_size=10, border=4).get_image()
    await update.effective_message.reply_photo(to_png(image), caption="🔳 Código QR generado")


@handle_errors("Error al generar el color")
async def color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Genera un color hexadecimal aleatorio con vista previa."""
    hex_color: str = f"#{random.randint(0, 0xFFFFFF):06X}"
    r, g, b = hex_to_rgb(hex_color)
    await update.effective_message.reply_photo(
        to_png(draw_swatches([hex_color])), caption=f"🎨 <code>{hex_color}</code>\nRGB({r}, {g}, {b})"
    )


@handle_errors("Error al generar la paleta")
async def palette(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Genera una paleta armónica de 3 a 5 colores aleatorios."""
    args: str = get_args(update)
    if args and args not in ("3", "4", "5"):
        raise usage("/palette [3-5]")
    count: int = int(args) if args else random.randint(3, 5)
    base_hue: float = random.random()
    hue_step: float = random.uniform(0.04, 0.33)
    colors: list[str] = [
        hls_to_hex(base_hue + i * hue_step, random.uniform(0.35, 0.75), random.uniform(0.45, 0.9)) for i in range(count)
    ]
    await update.effective_message.reply_photo(
        to_png(draw_swatches(colors)), caption="🎨 " + " · ".join(f"<code>{c}</code>" for c in colors)
    )


def build_identicon(seed: str) -> Image.Image:
    """Genera un identicon simétrico al estilo de GitHub a partir de una semilla."""
    digest: bytes = hashlib.sha256(seed.encode()).digest()
    fill: str = hls_to_hex(digest[0] / 255, 0.45 + digest[1] / 255 * 0.2, 0.45 + digest[2] / 255 * 0.4)
    size: int = AVATAR_GRID * AVATAR_CELL + 2 * AVATAR_MARGIN
    image: Image.Image = Image.new("RGB", (size, size), AVATAR_BACKGROUND)
    draw: ImageDraw.ImageDraw = ImageDraw.Draw(image)
    half: int = (AVATAR_GRID + 1) // 2
    for row in range(AVATAR_GRID):
        for column in range(half):
            if digest[3 + row * half + column] % 2 == 0:
                continue
            # Espejo horizontal para la simetría.
            for x in {column, AVATAR_GRID - 1 - column}:
                left: int = AVATAR_MARGIN + x * AVATAR_CELL
                top: int = AVATAR_MARGIN + row * AVATAR_CELL
                draw.rectangle((left, top, left + AVATAR_CELL - 1, top + AVATAR_CELL - 1), fill=fill)
    return image


@handle_errors("Error al generar el avatar")
async def avatar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Genera un avatar a partir de una semilla de texto."""
    seed: str = get_args(update) or update.effective_user.username or str(update.effective_user.id)
    await update.effective_message.reply_photo(to_png(build_identicon(seed)), caption="👤 Avatar generado")
