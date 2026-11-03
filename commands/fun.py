import html
import os
import random
import re
from datetime import datetime
from io import BytesIO

from PIL import Image
from telegram import Update
from telegram.ext import ContextTypes

from decorators import UserError, handle_errors
from utils import fetch_bytes, fetch_json, get_timezone, truncate

POKEAPI_URL = "https://pokeapi.co/api/v2"
WIKIPEDIA_RANDOM_URL = "https://es.wikipedia.org/api/rest_v1/page/random/summary"
JOKE_URL = "https://v2.jokeapi.dev/joke/Any"
JOKE_BLACKLIST = "nsfw,religious,political,racist,sexist,explicit"
QUOTE_URL = "https://zenquotes.io/api/random"
TMDB_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_URL = "https://image.tmdb.org/t/p/w500"
TVMAZE_URL = "https://api.tvmaze.com/shows"
ONTHISDAY_URL = "https://api.wikimedia.org/feed/v1/wikipedia/es/onthisday/selected/{month:02d}/{day:02d}"
EPHEMERIS_LIMIT = 10
SPRITE_SCALE = 4

POKEMON_TYPES = {
    "normal": "Normal",
    "fire": "Fuego",
    "water": "Agua",
    "electric": "Eléctrico",
    "grass": "Planta",
    "ice": "Hielo",
    "fighting": "Lucha",
    "poison": "Veneno",
    "ground": "Tierra",
    "flying": "Volador",
    "psychic": "Psíquico",
    "bug": "Bicho",
    "rock": "Roca",
    "ghost": "Fantasma",
    "dragon": "Dragón",
    "dark": "Siniestro",
    "steel": "Acero",
    "fairy": "Hada",
    "stellar": "Astral",
}
POKEMON_STATS = {
    "hp": "❤️ PS",
    "attack": "⚔️ Ataque",
    "defense": "🛡️ Defensa",
    "special-attack": "✨ At. Esp.",
    "special-defense": "🔰 Def. Esp.",
    "speed": "💨 Velocidad",
}


async def reply_with_photo(update: Update, photo: str | BytesIO | None, caption: str) -> None:
    """Envía una foto con pie o, si no hay imagen, solo el texto."""
    if photo:
        await update.effective_message.reply_photo(photo, caption=caption)
    else:
        await update.effective_message.reply_text(caption)


def upscale_sprite(data: bytes) -> BytesIO:
    """Amplía un sprite sin suavizado para conservar el pixel art."""
    sprite: Image.Image = Image.open(BytesIO(data)).convert("RGBA")
    sprite = sprite.resize((sprite.width * SPRITE_SCALE, sprite.height * SPRITE_SCALE), Image.Resampling.NEAREST)
    background: Image.Image = Image.new("RGBA", sprite.size, "WHITE")
    background.alpha_composite(sprite)
    buffer: BytesIO = BytesIO()
    background.convert("RGB").save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


@handle_errors("Error al obtener el Pokémon")
async def pokemon(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra un Pokémon aleatorio con sus tipos, estadísticas y sprite."""
    count: int = (await fetch_json(f"{POKEAPI_URL}/pokemon-species", params={"limit": 1}))["count"]
    data: dict = await fetch_json(f"{POKEAPI_URL}/pokemon/{random.randint(1, count)}")
    types: str = " / ".join(POKEMON_TYPES.get(t["type"]["name"], t["type"]["name"]) for t in data["types"])
    stats: str = "\n".join(
        f"{POKEMON_STATS.get(s['stat']['name'], s['stat']['name'])}: {s['base_stat']}" for s in data["stats"]
    )
    caption: str = (
        f"🎮 <b>#{data['id']} {html.escape(data['name'].title())}</b>\n"
        f"🏷️ Tipo: {types}\n"
        f"📏 {data['height'] / 10:g} m · ⚖️ {data['weight'] / 10:g} kg\n\n{stats}"
    )
    sprite_url: str | None = data["sprites"]["front_default"]
    await reply_with_photo(update, upscale_sprite(await fetch_bytes(sprite_url)) if sprite_url else None, caption)


@handle_errors("Error al obtener el artículo de Wikipedia")
async def wiki(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra un artículo aleatorio de Wikipedia con su resumen."""
    data: dict = await fetch_json(WIKIPEDIA_RANDOM_URL)
    title: str = html.escape(data["title"])
    url: str = html.escape(data["content_urls"]["desktop"]["page"])
    extract: str = html.escape(truncate(data.get("extract", ""), 600))
    caption: str = f'📚 <b>{title}</b>\n\n{extract}\n\n🔗 <a href="{url}">Leer en Wikipedia</a>'
    await reply_with_photo(update, data.get("thumbnail", {}).get("source"), caption)


@handle_errors("Error al obtener el chiste")
async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Devuelve un chiste aleatorio en español."""
    data: dict = await fetch_json(JOKE_URL, params={"lang": "es", "blacklistFlags": JOKE_BLACKLIST})
    if data.get("error"):
        raise UserError("No hay chistes disponibles ahora mismo")
    text: str = (
        html.escape(data["joke"])
        if data["type"] == "single"
        else f"{html.escape(data['setup'])}\n\n<tg-spoiler>{html.escape(data['delivery'])}</tg-spoiler>"
    )
    await update.effective_message.reply_text(f"😂 {text}")


@handle_errors("Error al obtener la cita")
async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra una cita célebre aleatoria con su autor."""
    data: dict = (await fetch_json(QUOTE_URL))[0]
    await update.effective_message.reply_text(
        f"💬 <i>«{html.escape(data['q'])}»</i>\n\n— <b>{html.escape(data['a'])}</b>"
    )


async def random_tmdb(api_key: str, kind: str) -> tuple[str | None, str]:
    """Elige una película ("movie") o serie ("tv") popular aleatoria de TMDB."""
    data: dict = await fetch_json(
        f"{TMDB_URL}/discover/{kind}",
        params={
            "api_key": api_key,
            "language": "es-ES",
            "sort_by": "popularity.desc",
            "vote_count.gte": 1000,
            "page": random.randint(1, 20),
        },
    )
    item: dict = random.choice(data["results"])
    title: str = item.get("title") or item.get("name")
    released: str = (item.get("release_date") or item.get("first_air_date") or "")[:4]
    caption: str = (
        f"{'🎬 Película' if kind == 'movie' else '📺 Serie'}: <b>{html.escape(title)}</b> ({released})\n"
        f"⭐ {item['vote_average']:.1f}/10\n\n"
        f"{html.escape(truncate(item.get('overview') or 'Sin sinopsis.', 500))}\n\n"
        f'🔗 <a href="https://www.themoviedb.org/{kind}/{item["id"]}">Ver en TMDB</a>'
    )
    poster: str | None = f"{TMDB_IMAGE_URL}{item['poster_path']}" if item.get("poster_path") else None
    return poster, caption


async def random_tvmaze() -> tuple[str | None, str]:
    """Elige una serie bien valorada aleatoria de TVmaze."""
    shows: list[dict] = await fetch_json(TVMAZE_URL, params={"page": random.randint(0, 250)})
    candidates: list[dict] = [
        s for s in shows if ((s.get("rating") or {}).get("average") or 0) >= 7 and s.get("image") and s.get("summary")
    ] or shows
    show: dict = random.choice(candidates)
    summary: str = re.sub(r"<[^>]+>", "", show.get("summary") or "Sin sinopsis.")
    caption: str = (
        f"📺 Serie: <b>{html.escape(show['name'])}</b> ({(show.get('premiered') or '')[:4]})\n"
        f"⭐ {(show.get('rating') or {}).get('average') or 'N/D'}/10\n\n"
        f"{html.escape(truncate(summary, 500))}\n\n"
        f'🔗 <a href="{html.escape(show["url"])}">Ver en TVmaze</a>'
    )
    return (show.get("image") or {}).get("original"), caption


@handle_errors("Error al recomendar una película")
async def film(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Recomienda una película aleatoria con sinopsis, nota y cartel."""
    api_key: str | None = os.getenv("TMDB_API_KEY")
    if not api_key:
        raise UserError("Falta configurar TMDB_API_KEY para recomendar películas")
    await reply_with_photo(update, *await random_tmdb(api_key, "movie"))


@handle_errors("Error al recomendar una serie")
async def series(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Recomienda una serie aleatoria con sinopsis, nota y cartel."""
    api_key: str | None = os.getenv("TMDB_API_KEY")
    await reply_with_photo(update, *await (random_tmdb(api_key, "tv") if api_key else random_tvmaze()))


@handle_errors("Error al obtener las efemérides")
async def ephemeris(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra hechos históricos destacados ocurridos un día como hoy."""
    today: datetime = datetime.now(get_timezone(context.user_data.get("timezone")))
    data: dict = await fetch_json(ONTHISDAY_URL.format(month=today.month, day=today.day))
    selected: list[dict] = data.get("selected", [])
    if not selected:
        raise UserError("No hay efemérides para hoy")
    events: list[dict] = sorted(random.sample(selected, min(EPHEMERIS_LIMIT, len(selected))), key=lambda e: e["year"])
    lines: list[str] = [f"• <b>{event['year']}</b> — {html.escape(truncate(event['text'], 300))}" for event in events]
    await update.effective_message.reply_text(
        f"📅 <b>Efemérides del {today.day:02d}/{today.month:02d}</b>\n\n" + "\n\n".join(lines)
    )
