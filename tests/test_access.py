import pytest
from telegram.ext import ApplicationHandlerStop

from main import NO_ACCESS, restrict_access
from tests.conftest import reply


@pytest.fixture(autouse=True)
def authorized_user(monkeypatch):
    monkeypatch.setenv("USER_ID", "42")


async def test_authorized_user_passes(make_update):
    update, context = make_update("/help")
    update.effective_user.id = 42
    await restrict_access(update, context)
    update.effective_message.reply_text.assert_not_called()


async def test_other_user_gets_no_access(make_update):
    update, context = make_update("/help")
    update.effective_user.id = 7
    update.callback_query = None
    with pytest.raises(ApplicationHandlerStop):
        await restrict_access(update, context)
    assert reply(update) == NO_ACCESS


async def test_other_user_button_gets_alert(make_update):
    update, context = make_update("")
    update.effective_user.id = 7
    with pytest.raises(ApplicationHandlerStop):
        await restrict_access(update, context)
    update.callback_query.answer.assert_called_once_with(NO_ACCESS, show_alert=True)
    update.effective_message.reply_text.assert_not_called()
