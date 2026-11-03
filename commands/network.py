import asyncio
import html
import time
from datetime import datetime

import httpx
import whois
from telegram import Update
from telegram.ext import ContextTypes

from decorators import UserError, handle_errors
from utils import extract_host, get_args, http_client, resolve_public_ip, usage

PING_ATTEMPTS = 4
PING_TIMEOUT = 3
PING_PORTS = (443, 80)
MAX_HEADERS_LENGTH = 3500
MAX_HEADER_VALUE = 200


async def tcp_latency(ip: str, port: int) -> float | None:
    """Mide en ms lo que tarda en abrirse una conexión TCP."""
    start: float = time.perf_counter()
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), PING_TIMEOUT)
    except (TimeoutError, OSError):
        return None
    latency: float = (time.perf_counter() - start) * 1000
    writer.close()
    return latency


@handle_errors("Error al hacer ping")
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comprueba la latencia y disponibilidad de un dominio o IP."""
    target: str = get_args(update)
    if not target:
        raise usage("/ping <dominio>")
    host: str = extract_host(target)
    ip: str = await asyncio.to_thread(resolve_public_ip, host)

    for port in PING_PORTS:
        latencies: list[float] = [
            latency for _ in range(PING_ATTEMPTS) if (latency := await tcp_latency(ip, port)) is not None
        ]
        if latencies:
            break
    else:
        await update.effective_message.reply_text(
            f"🔴 <b>{html.escape(host)}</b> ({ip}) no responde en los puertos {', '.join(map(str, PING_PORTS))}"
        )
        return

    await update.effective_message.reply_text(
        f"🟢 <b>{html.escape(host)}</b> ({ip}) disponible\n\n"
        f"🔌 Puerto TCP: {port}\n"
        f"📦 Respuestas: {len(latencies)}/{PING_ATTEMPTS}\n"
        f"⏱️ Latencia: mín {min(latencies):.1f} ms · media {sum(latencies) / len(latencies):.1f} ms"
        f" · máx {max(latencies):.1f} ms"
    )


def first_value(value: object) -> object:
    """Devuelve el primer elemento si el valor es una lista."""
    return value[0] if isinstance(value, list) and value else value


def format_whois_value(value: object) -> str:
    """Formatea un valor de WHOIS para mostrarlo."""
    value = first_value(value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return html.escape(str(value))


@handle_errors("Error al consultar el WHOIS")
async def whois_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Devuelve la información básica de registro de un dominio."""
    target: str = get_args(update)
    if not target:
        raise usage("/whois <dominio>")
    domain: str = extract_host(target)
    try:
        data: dict = await asyncio.to_thread(whois.whois, domain, quiet=True)
    except whois.parser.WhoisDomainNotFoundError:
        data = {}
    if not data.get("domain_name"):
        raise UserError(f"No hay datos WHOIS para <b>{html.escape(domain)}</b>")

    fields: list[tuple[str, str]] = [
        ("🌐 Dominio", "domain_name"),
        ("🏢 Registrador", "registrar"),
        ("👤 Organización", "org"),
        ("🌍 País", "country"),
        ("📅 Creado", "creation_date"),
        ("🔄 Actualizado", "updated_date"),
        ("⌛ Expira", "expiration_date"),
    ]
    lines: list[str] = [f"{label}: {format_whois_value(data[key])}" for label, key in fields if data.get(key)]
    name_servers = data.get("name_servers")
    if name_servers:
        servers: list[str] = sorted(
            {server.lower() for server in ([name_servers] if isinstance(name_servers, str) else name_servers)}
        )
        lines.append("🖧 DNS: " + ", ".join(map(html.escape, servers)))
    await update.effective_message.reply_text("\n".join(lines))


@handle_errors("Error al obtener las cabeceras")
async def headers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Obtiene las cabeceras HTTP que responde una URL."""
    target: str = get_args(update)
    if not target:
        raise usage("/headers <url>")
    url: str = target if "://" in target else f"https://{target}"
    if not url.startswith(("http://", "https://")):
        raise UserError("Solo se admiten URLs http o https")
    await asyncio.to_thread(resolve_public_ip, extract_host(url))

    # Sin seguir redirecciones para no saltar a destinos internos.
    async with http_client(follow_redirects=False) as client:
        try:
            response: httpx.Response = await client.head(url)
            if response.status_code == 405:
                response = await client.get(url)
        except httpx.HTTPError as e:
            raise UserError(f"No se pudo conectar: {html.escape(str(e) or type(e).__name__)}") from None

    lines: str = html.escape(
        "\n".join(
            f"{name}: {value if len(value) <= MAX_HEADER_VALUE else value[:MAX_HEADER_VALUE] + '…'}"
            for name, value in response.headers.items()
        )
    )
    if len(lines) > MAX_HEADERS_LENGTH:
        lines = lines[: lines.rfind("\n", 0, MAX_HEADERS_LENGTH)] + "\n…"
    await update.effective_message.reply_text(
        f"🌐 <b>{response.status_code} {html.escape(response.reason_phrase)}</b> · {html.escape(url)}\n\n"
        f"<pre>{lines}</pre>"
    )
