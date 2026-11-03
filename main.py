#!/usr/bin/env python3

import html
import os
import re
import sys

from dataclasses import dataclass
from dotenv import load_dotenv
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    Defaults,
    MessageHandler,
    filters,
)

from commands import conversion, finance, fun, maths, media, network, security, text, weather
from decorators import Handler, handle_errors, print_styled


@dataclass(frozen=True)
class Command:
    names: tuple[str, ...]
    callback: Handler
    usage: str
    description: str


@handle_errors("Error al mostrar la bienvenida")
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra la bienvenida y un resumen de funciones."""
    name: str = html.escape(update.effective_user.first_name if update.effective_user else "")
    summary: str = "\n".join(
        f"{title} — {len(commands)} comando(s)" for title, commands in CATEGORIES
    )
    await update.effective_message.reply_text(
        f"👋 ¡Hola, <b>{name}</b>! Soy un bot multiusos.\n\n{summary}\n\n"
        "Pulsen el botón o usen /help para ver todos los comandos.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📖 Ayuda", callback_data="help:menu")]])
    )


def help_menu() -> tuple[str, InlineKeyboardMarkup]:
    """Construye el menú principal de ayuda."""
    buttons: list[InlineKeyboardButton] = [
        InlineKeyboardButton(title, callback_data=f"help:{index}")
        for index, (title, _) in enumerate(CATEGORIES)
    ]
    rows: list[list[InlineKeyboardButton]] = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return "📖 <b>Ayuda</b>\n\nElijan una categoría:", InlineKeyboardMarkup(rows)


def help_category(index: int) -> tuple[str, InlineKeyboardMarkup]:
    """Construye la ayuda de una categoría."""
    title, commands = CATEGORIES[index]
    lines: list[str] = [
        f"<code>{html.escape(command.usage)}</code>\n{command.description}" for command in commands
    ]
    back: InlineKeyboardMarkup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Volver", callback_data="help:menu")]]
    )
    return f"<b>{title}</b>\n\n" + "\n\n".join(lines), back


@handle_errors("Error al mostrar la ayuda")
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra el menú interactivo de ayuda."""
    text, markup = help_menu()
    await update.effective_message.reply_text(text, reply_markup=markup)


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Navega por el menú de ayuda."""
    query = update.callback_query
    await query.answer()
    section: str = query.data.removeprefix("help:")
    text, markup = help_menu() if section == "menu" else help_category(int(section))
    await query.edit_message_text(text, reply_markup=markup)


CATEGORIES: list[tuple[str, list[Command]]] = [
    ("⛅ Tiempo y Clima", [
        Command(("weather", "tiempo"), weather.weather, "/weather [ciudad]",
                "Tiempo actual de una ciudad o de su ubicación"),
    ]),
    ("📝 Utilidades de Texto", [
        Command(("count_words", "count-words"), text.count_words, "/count_words <texto>",
                "Cuenta las palabras de un texto"),
        Command(("count_letter", "count-letter"), text.count_letters, "/count_letter <texto>",
                "Cuenta los caracteres con y sin espacios"),
        Command(("lorem", "loremipsum"), text.lorem, "/lorem <palabras>",
                "Genera un texto Lorem Ipsum"),
    ]),
    ("🔄 Conversores", [
        Command(("conversion", "convert"), conversion.conversion, "/conversion <cantidad> <origen> <destino>",
                "Convierte divisas (EUR a USD), medidas (km a mi) o tiempo (horas a min)"),
    ]),
    ("🛡️ Ciberseguridad", [
        Command(("password",), security.password, "/password <longitud>",
                "Genera una contraseña segura y aleatoria"),
        Command(("hash",), security.hash_text, "/hash <texto>", "Hashes MD5, SHA-256 y SHA-512 de un texto"),
        Command(("base64_encode",), security.base64_encode, "/base64_encode <texto>",
                "Codifica un texto en Base64"),
        Command(("base64_decode",), security.base64_decode, "/base64_decode <codigo>",
                "Decodifica un texto en Base64"),
        Command(("id",), security.show_id, "/id", "ID de Telegram del usuario y del chat"),
    ]),
    ("🧮 Matemáticas", [
        Command(("calculate", "calc"), maths.calculate, "/calculate <expresion>",
                "Evalúa una expresión matemática, ej. 2*(5+3)^2"),
        Command(("prime",), maths.prime, "/prime <numero>", "Comprueba si un número es primo"),
        Command(("fibonacci", "fibbonacci"), maths.fibonacci, "/fibonacci <numero>",
                "Calcula el n-ésimo número de Fibonacci"),
        Command(("percent",), maths.percent, "/percent <parte> <total>",
                "Porcentaje que representa una parte sobre el total"),
    ]),
    ("🖼️ Medios y Códigos", [
        Command(("qr",), media.qr, "/qr <texto_o_url>", "Genera un código QR"),
        Command(("color",), media.color, "/color", "Color hexadecimal aleatorio con vista previa"),
        Command(("palette",), media.palette, "/palette [3-5]", "Paleta de 3 a 5 colores con vista previa"),
        Command(("avatar",), media.avatar, "/avatar <semilla>", "Avatar estilo GitHub a partir de una semilla"),
    ]),
    ("📈 Finanzas y Criptomonedas", [
        Command(("crypto",), finance.crypto, "/crypto <simbolo>",
                "Precio, variación 24h y volumen de una criptomoneda"),
        Command(("currency", "moneda"), finance.currency, "/currency <simbolo>",
                "Cambio actual y variación de una moneda (€, EUR, euro...)"),
        Command(("financial_market", "financial-market"), finance.financial_market, "/financial_market",
                "Resumen de los principales índices y criptomonedas"),
    ]),
    ("🌐 Redes y Desarrollo", [
        Command(("ping",), network.ping, "/ping <dominio>", "Latencia y disponibilidad de un sitio web o IP"),
        Command(("whois",), network.whois_lookup, "/whois <dominio>", "Información de registro de un dominio"),
        Command(("headers",), network.headers, "/headers <url>", "Cabeceras HTTP que responde una página"),
    ]),
    ("🎮 Entretenimiento", [
        Command(("pokemon",), fun.pokemon, "/pokemon", "Pokémon aleatorio con tipos, estadísticas y sprite"),
        Command(("wiki",), fun.wiki, "/wiki", "Artículo aleatorio de Wikipedia con resumen y enlace"),
        Command(("joke",), fun.joke, "/joke", "Chiste aleatorio"),
        Command(("quote",), fun.quote, "/quote", "Cita célebre aleatoria con su autor"),
        Command(("film",), fun.film, "/film", "Película o serie aleatoria con sinopsis, nota y cartel"),
        Command(("ephemeris",), fun.ephemeris, "/ephemeris", "Hechos históricos de un día como hoy"),
    ]),
    ("⚙️ Sistema", [
        Command(("start",), start, "/start", "Bienvenida y resumen de funciones"),
        Command(("help",), help_command, "/help", "Menú interactivo de ayuda"),
    ]),
]

VALID_COMMAND = re.compile(r"^[a-z0-9_]{1,32}$")


def register_commands(application: Application) -> None:
    """Registra los comandos; los nombres con guion se capturan por regex."""
    for _, commands in CATEGORIES:
        for command in commands:
            valid: list[str] = [name for name in command.names if VALID_COMMAND.match(name)]
            hyphenated: list[str] = [name for name in command.names if name not in valid]
            if valid:
                application.add_handler(CommandHandler(valid, command.callback))
            if hyphenated:
                pattern: str = "|".join(map(re.escape, hyphenated))
                application.add_handler(MessageHandler(
                    filters.Regex(rf"^/({pattern})(@\w+)?(\s|$)"), command.callback
                ))
    application.add_handler(MessageHandler(filters.LOCATION, weather.weather_location))
    application.add_handler(CallbackQueryHandler(help_callback, pattern=r"^help:"))


async def post_init(application: Application) -> None:
    """Publica la lista de comandos en el menú de Telegram."""
    await application.bot.set_my_commands([
        BotCommand(command.names[0], command.description)
        for _, commands in CATEGORIES for command in commands
    ])


async def log_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra en consola los errores no controlados."""
    print_styled(message=f"{context.error}\n", error_type=type(context.error).__name__, color="red")


def main():
    """Función principal que arranca el bot."""
    load_dotenv()
    token: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print_styled(message="Falta TELEGRAM_BOT_TOKEN en .env\n", error_type="ValueError", color="red")
        sys.exit(1)

    application: Application = (
        Application.builder()
        .token(token)
        .defaults(Defaults(
            parse_mode=ParseMode.HTML,
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        ))
        .post_init(post_init)
        .build()
    )
    register_commands(application=application)
    application.add_error_handler(log_error)

    print_styled(message="✓ Bot iniciado. Pulsen Ctrl+C para detenerlo.\n", color="green")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
