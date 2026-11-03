import asyncio
import html
import ipaddress
import ssl
import time
from datetime import UTC, datetime
from urllib.parse import quote

import httpx
import whois
from telegram import Update
from telegram.ext import ContextTypes

from decorators import UserError, handle_errors
from utils import extract_host, fetch_json, get_args, http_client, resolve_public_ip, usage

PING_ATTEMPTS = 4
PING_TIMEOUT = 3
PING_PORTS = (443, 80)
MAX_HEADERS_LENGTH = 3500
MAX_HEADER_VALUE = 200
# shortcut: ip-api gratis solo admite HTTP; pasar a la versión de pago si hace falta HTTPS
IP_API_URL = "http://ip-api.com/json/{target}"
IP_API_FIELDS = "status,message,query,country,regionName,city,zip,lat,lon,timezone,isp,org,as"
SSL_TIMEOUT = 10
DNS_URL = "https://dns.google/resolve"
DNS_TYPES = {"A": 1, "AAAA": 28, "CNAME": 5, "MX": 15, "NS": 2, "TXT": 16}
MAX_DNS_VALUE = 200
MAX_DNS_RECORDS = 10


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


@handle_errors("Error al consultar la IP")
async def ip_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra la geolocalización y el proveedor de una IP o dominio."""
    target: str = get_args(update)
    if not target:
        raise usage("/ip <ip o dominio>")
    try:
        host: str = str(ipaddress.ip_address(target))
    except ValueError:
        host = extract_host(target)
    data: dict = await fetch_json(
        IP_API_URL.format(target=quote(host, safe="")), params={"lang": "es", "fields": IP_API_FIELDS}
    )
    if data.get("status") != "success":
        raise UserError(f"No hay datos para <b>{html.escape(host)}</b> ({html.escape(data.get('message', '?'))})")
    location: str = ", ".join(filter(None, [data.get("city"), data.get("regionName"), data.get("country")]))
    await update.effective_message.reply_text(
        f"🌐 <b>{html.escape(data['query'])}</b>\n\n"
        f"📍 Ubicación: {html.escape(location or 'N/D')} {html.escape(data.get('zip') or '')}\n"
        f"🧭 Coordenadas: {data.get('lat')}, {data.get('lon')}\n"
        f"🕒 Zona horaria: {html.escape(data.get('timezone') or 'N/D')}\n"
        f"🏢 Proveedor: {html.escape(data.get('isp') or 'N/D')}\n"
        f"🏛️ Organización: {html.escape(data.get('org') or 'N/D')}\n"
        f"🔢 AS: {html.escape(data.get('as') or 'N/D')}"
    )


async def fetch_certificate(host: str, ip: str) -> dict:
    """Abre una conexión TLS validada y devuelve el certificado del servidor."""
    _, writer = await asyncio.wait_for(
        asyncio.open_connection(ip, 443, ssl=ssl.create_default_context(), server_hostname=host), SSL_TIMEOUT
    )
    certificate: dict = writer.get_extra_info("peercert")
    writer.close()
    return certificate


def certificate_name(entries: tuple) -> str:
    """Obtiene el nombre común u organización de un sujeto o emisor."""
    fields: dict[str, str] = dict(pair for entry in entries for pair in entry)
    return fields.get("commonName") or fields.get("organizationName") or "N/D"


@handle_errors("Error al comprobar el certificado")
async def ssl_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comprueba la validez y caducidad del certificado TLS de un dominio."""
    target: str = get_args(update)
    if not target:
        raise usage("/ssl <dominio>")
    host: str = extract_host(target)
    ip: str = await asyncio.to_thread(resolve_public_ip, host)
    try:
        certificate: dict = await fetch_certificate(host, ip)
    except ssl.SSLCertVerificationError as e:
        raise UserError(
            f"Certificado no válido para <b>{html.escape(host)}</b>: {html.escape(e.verify_message)}"
        ) from None
    except (OSError, TimeoutError):
        raise UserError(f"No se pudo conectar a <b>{html.escape(host)}</b> por el puerto 443") from None

    expires: float = ssl.cert_time_to_seconds(certificate["notAfter"])
    days: int = int((expires - time.time()) // 86400)
    status: str = "🟢" if days > 30 else "🟡" if days > 7 else "🔴"
    names: list[str] = [value for kind, value in certificate.get("subjectAltName", ()) if kind == "DNS"]
    issued: str = datetime.fromtimestamp(ssl.cert_time_to_seconds(certificate["notBefore"]), UTC).strftime("%Y-%m-%d")
    await update.effective_message.reply_text(
        f"🔒 <b>{html.escape(host)}</b> · {status} certificado válido\n\n"
        f"👤 Sujeto: {html.escape(certificate_name(certificate['subject']))}\n"
        f"🏢 Emisor: {html.escape(certificate_name(certificate['issuer']))}\n"
        f"📅 Emitido: {issued}\n"
        f"⌛ Expira: {datetime.fromtimestamp(expires, UTC):%Y-%m-%d} ({days} días)\n"
        f"🌐 Dominios: {len(names)} ({html.escape(', '.join(names[:5]))}{', …' if len(names) > 5 else ''})"
    )


async def dns_records(domain: str, record_type: str) -> list[str]:
    """Consulta un tipo de registro DNS mediante DNS sobre HTTPS."""
    data: dict = await fetch_json(DNS_URL, params={"name": domain, "type": record_type})
    if data.get("Status") == 3:
        raise UserError(f"El dominio <b>{html.escape(domain)}</b> no existe")
    return [
        answer["data"] if len(answer["data"]) <= MAX_DNS_VALUE else answer["data"][:MAX_DNS_VALUE] + "…"
        for answer in data.get("Answer", [])
        if answer["type"] == DNS_TYPES[record_type]
    ]


@handle_errors("Error al consultar el DNS")
async def dns(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra los registros DNS principales de un dominio."""
    target: str = get_args(update)
    if not target:
        raise usage("/dns <dominio>")
    domain: str = extract_host(target)
    results: list[list[str]] = await asyncio.gather(*(dns_records(domain, kind) for kind in DNS_TYPES))
    sections: list[str] = [
        f"<b>{kind}</b>\n"
        + "\n".join(f"• <code>{html.escape(value)}</code>" for value in values[:MAX_DNS_RECORDS])
        + (f"\n• … y {len(values) - MAX_DNS_RECORDS} más" if len(values) > MAX_DNS_RECORDS else "")
        for kind, values in zip(DNS_TYPES, results, strict=True)
        if values
    ]
    if not sections:
        raise UserError(f"No hay registros DNS para <b>{html.escape(domain)}</b>")
    await update.effective_message.reply_text(f"🖧 <b>DNS de {html.escape(domain)}</b>\n\n" + "\n\n".join(sections))
