from unittest.mock import AsyncMock, MagicMock

import pytest

from utils import cache


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


@pytest.fixture
def make_update():
    """Crea un update y un context falsos para llamar a los comandos."""

    def factory(text: str, user_data: dict | None = None):
        update = MagicMock()
        update.effective_message.text = text
        update.effective_message.reply_text = AsyncMock()
        update.effective_message.reply_photo = AsyncMock()
        update.callback_query.answer = AsyncMock()
        context = MagicMock()
        context.user_data = {} if user_data is None else user_data
        return update, context

    return factory


def reply(update) -> str:
    """Texto de la última respuesta enviada."""
    return update.effective_message.reply_text.call_args.args[0]
