import html
import ipaddress
import socket

import httpx

from telegram import Update
from typing import Any
from urllib.parse import urlparse

from decorators import UserError

USER_AGENT = "telegram-bot/1.0 (https://github.com/hectorOliSan/telegram-bot)"
TIMEOUT = 15


def get_args(update: Update) -> str:
    """Devuelve el texto que sigue al comando."""
    parts: list[str] = (update.effective_message.text or "").split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def usage(text: str) -> UserError:
    """Crea un error con el uso correcto del comando."""
    return UserError(f"Uso: <code>{html.escape(text)}</code>")


def parse_number(value: str) -> float:
    """Convierte un texto en número aceptando coma decimal."""
    try:
        return float(value.replace(",", "."))
    except ValueError:
        raise UserError(f"Número no válido: <code>{html.escape(value)}</code>")


def format_number(value: float, decimals: int = 2) -> str:
    """Formatea un número con separadores al estilo español."""
    formatted: str = f"{value:,.{decimals}f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def http_client(**kwargs: Any) -> httpx.AsyncClient:
    """Crea un cliente HTTP con la configuración común."""
    return httpx.AsyncClient(
        timeout=TIMEOUT,
        follow_redirects=kwargs.pop("follow_redirects", True),
        headers={"User-Agent": USER_AGENT, **kwargs.pop("headers", {})},
        **kwargs
    )


async def fetch_json(url: str, params: dict | None = None, headers: dict | None = None) -> Any:
    """Hace una petición GET y devuelve el JSON."""
    async with http_client(headers=headers or {}) as client:
        response: httpx.Response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def fetch_bytes(url: str) -> bytes:
    """Descarga un recurso binario."""
    async with http_client() as client:
        response: httpx.Response = await client.get(url)
        response.raise_for_status()
        return response.content


def extract_host(target: str) -> str:
    """Obtiene el host de un dominio, IP o URL."""
    host: str | None = urlparse(target if "://" in target else f"//{target}").hostname
    if not host:
        raise UserError(f"Destino no válido: <code>{html.escape(target)}</code>")
    return host


def resolve_public_ip(host: str) -> str:
    """Resuelve el host y rechaza IPs privadas o reservadas."""
    try:
        ip: str = socket.gethostbyname(host)
    except socket.gaierror:
        raise UserError(f"No se pudo resolver <code>{html.escape(host)}</code>")
    if not ipaddress.ip_address(ip).is_global:
        raise UserError("Solo se permiten destinos públicos")
    return ip
