from collections.abc import Awaitable, Callable
from functools import wraps

from rich.console import Console
from telegram import Update
from telegram.ext import ContextTypes

Handler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]
console = Console()


class UserError(Exception):
    """Error de entrada del usuario que se le muestra tal cual."""


def print_styled(message: str, error_type: str | None = None, color: str = "white") -> None:
    """Imprime un mensaje con estilo usando rich."""
    console.print(f"[{color}]{f'❌ ({error_type}) ' if error_type else ''}{message}[/{color}]")


def handle_errors(error_message: str) -> Callable[[Handler], Handler]:
    """Decorador para manejar excepciones de los comandos y avisar al usuario."""

    def decorator(func: Handler) -> Handler:
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            try:
                await func(update, context)
            except UserError as e:
                await update.effective_message.reply_text(f"⚠️ {e}")
            except Exception as e:
                print_styled(message=f"{error_message}: {str(e)}\n", error_type=type(e).__name__, color="red")
                await update.effective_message.reply_text(f"❌ {error_message}")

        return wrapper

    return decorator
