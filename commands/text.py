import html
import random
import re

from telegram import Update
from telegram.ext import ContextTypes

from decorators import UserError, handle_errors
from utils import fetch_json, get_args, usage

TRANSLATE_URL = "https://api.mymemory.translated.net/get"
TRANSLATE_MAX_BYTES = 500
LANGUAGE_CODE = re.compile(r"[a-z]{2,3}(-[a-z]{2,4})?", re.IGNORECASE)
LOREM_START = "Lorem ipsum dolor sit amet, consectetur adipiscing elit".split()
LOREM_WORDS = (
    "a ac accumsan aenean aliquam aliquet amet ante arcu at auctor augue blandit commodo condimentum "
    "congue consequat convallis cras curabitur cursus dapibus diam dictum dignissim dolor donec dui duis "
    "egestas eget eleifend elementum elit enim erat eros est et etiam eu euismod facilisis fames faucibus "
    "felis fermentum feugiat fringilla fusce gravida habitant hendrerit iaculis id imperdiet in integer "
    "interdum ipsum justo lacinia lacus laoreet lectus leo libero ligula lobortis lorem luctus maecenas "
    "magna malesuada massa mattis mauris metus mi molestie mollis morbi nam nec neque netus nibh nisi nisl "
    "non nulla nunc odio orci ornare pellentesque pharetra phasellus placerat porta porttitor posuere "
    "praesent pretium proin pulvinar purus quam quis quisque rhoncus risus rutrum sagittis sapien "
    "scelerisque sed sem semper senectus sit sodales sollicitudin suscipit suspendisse tellus tempor "
    "tempus tincidunt tortor tristique turpis ullamcorper ultrices ultricies urna ut varius vehicula vel "
    "velit venenatis vestibulum vitae vivamus viverra volutpat vulputate"
).split()
LOREM_DEFAULT = 50
LOREM_MAX = 500


@handle_errors("Error al contar las palabras")
async def count_words(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cuenta las palabras de un texto."""
    text: str = get_args(update)
    if not text:
        raise usage("/count_words <texto>")
    await update.effective_message.reply_text(f"📝 Palabras: <b>{len(text.split())}</b>")


@handle_errors("Error al contar los caracteres")
async def count_letters(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cuenta los caracteres de un texto con y sin espacios."""
    text: str = get_args(update)
    if not text:
        raise usage("/count_letter <texto>")
    without_spaces: int = len("".join(text.split()))
    await update.effective_message.reply_text(
        f"🔤 Caracteres (con espacios): <b>{len(text)}</b>\n🔡 Caracteres (sin espacios): <b>{without_spaces}</b>"
    )


def generate_lorem(word_count: int) -> str:
    """Genera un texto Lorem Ipsum con el número de palabras indicado."""
    words: list[str] = (LOREM_START + random.choices(LOREM_WORDS, k=max(0, word_count - len(LOREM_START))))[:word_count]
    sentences: list[str] = []
    while words:
        length: int = random.randint(6, 14)
        sentence, words = words[:length], words[length:]
        sentences.append(" ".join(sentence).capitalize() + ".")
    return " ".join(sentences)


@handle_errors("Error al generar el texto Lorem Ipsum")
async def lorem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Genera un texto Lorem Ipsum de la longitud deseada."""
    args: str = get_args(update)
    if args and not args.isdigit():
        raise usage("/lorem <palabras>")
    word_count: int = int(args) if args else LOREM_DEFAULT
    if not 1 <= word_count <= LOREM_MAX:
        raise UserError(f"El número de palabras debe estar entre 1 y {LOREM_MAX}")
    await update.effective_message.reply_text(generate_lorem(word_count))


@handle_errors("Error al traducir el texto")
async def translate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Traduce un texto al idioma indicado detectando el idioma de origen."""
    parts: list[str] = get_args(update).split(maxsplit=1)
    if len(parts) < 2 or not LANGUAGE_CODE.fullmatch(parts[0]):
        raise usage("/translate <idioma> <texto>  (ej. /translate en hola mundo)")
    target, text = parts
    if len(text.encode()) > TRANSLATE_MAX_BYTES:
        raise UserError(f"El texto no puede superar {TRANSLATE_MAX_BYTES} bytes")
    data: dict = await fetch_json(TRANSLATE_URL, params={"q": text, "langpair": f"autodetect|{target}"})
    if str(data.get("responseStatus")) != "200":
        raise UserError(f"No se pudo traducir a <code>{html.escape(target)}</code>: usen un código como en, fr o zh-CN")
    result: dict = data["responseData"]
    source: str = result.get("detectedLanguage") or "?"
    await update.effective_message.reply_text(
        f"🌍 <b>{html.escape(source)} → {html.escape(target.lower())}</b>\n\n"
        f"{html.escape(html.unescape(result['translatedText']))}"
    )
