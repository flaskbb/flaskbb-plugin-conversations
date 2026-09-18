"""Tests for the conversation views as the message pages' htmx requests
drive them.

The views are invoked directly rather than over HTTP, which skips the
blueprint's before-request handlers - they are orthogonal to what is tested
here.
"""

import pytest
from flask import get_flashed_messages, url_for
from flask_login import login_user, logout_user
from flaskbb.extensions import db

from conversations import views
from conversations.forms import ConversationForm
from conversations.models import Conversation


def _htmx_post(application, view, actor, current_url, **kwargs):
    headers = {"HX-Request": "true", "HX-Current-URL": f"http://localhost{current_url}"}

    with application.test_request_context(method="POST", headers=headers):
        login_user(actor)
        response = view(**kwargs)
        messages = get_flashed_messages(with_categories=True)
        logout_user()

    return response, messages


def test_move_to_trash_returns_to_the_page_it_was_sent_from(application, conversation, user):
    page = "/conversations/sent?page=2"

    response, _messages = _htmx_post(
        application,
        views.MoveConversation.as_view("move_conversation"),
        user,
        page,
        conversation_id=conversation.id,
    )

    assert response.status_code == 302
    assert response.headers["Location"] == page
    assert conversation.trash


def test_delete_returns_to_the_page_it_was_sent_from(application, conversation, user):
    conversation.trash = True
    conversation.save()
    conversation_id = conversation.id
    page = "/conversations/trash"

    response, _messages = _htmx_post(
        application,
        views.DeleteConversation.as_view("delete_conversation"),
        user,
        page,
        conversation_id=conversation_id,
    )

    assert response.status_code == 302
    assert response.headers["Location"] == page
    assert db.session.get(Conversation, conversation_id) is None


def test_reply_over_the_quota_loads_the_inbox(application, conversation, user, monkeypatch):
    monkeypatch.setattr(
        views,
        "flaskbb_config",
        {"CONVERSATIONS_MESSAGE_QUOTA_ENABLED": True, "CONVERSATIONS_MESSAGE_QUOTA": 0},
    )

    response, messages = _htmx_post(
        application,
        views.ViewConversation.as_view("view_conversation"),
        user,
        f"/conversations/{conversation.id}/view",
        conversation_id=conversation.id,
    )

    with application.test_request_context():
        inbox = url_for("conversations_bp.inbox")

    assert response.status_code == 204
    assert response.headers["HX-Redirect"] == inbox
    assert (
        "danger",
        "You cannot send any messages anymore because you have reached your message limit.",
    ) in messages


def test_inbox_actions_refresh_the_message_content(
    application, default_settings, conversation_msgs, user
):
    with application.test_request_context():
        login_user(user)
        response = views.Inbox.as_view("inbox")()
        logout_user()

    assert 'id="message-content"' in response
    assert 'hx-target="#message-content"' in response
    assert f'hx-post="/conversations/{conversation_msgs.id}/move"' in response


QUOTA_EXCEEDED = (
    "danger",
    "You cannot send any messages anymore because you have reached your message limit.",
)


@pytest.fixture
def no_csrf(application):
    previous = application.config.get("WTF_CSRF_ENABLED", True)
    application.config["WTF_CSRF_ENABLED"] = False
    yield
    application.config["WTF_CSRF_ENABLED"] = previous


@pytest.fixture
def no_quota(monkeypatch):
    monkeypatch.setattr(
        views,
        "flaskbb_config",
        {"CONVERSATIONS_MESSAGE_QUOTA_ENABLED": True, "CONVERSATIONS_MESSAGE_QUOTA": 0},
    )


def _send(application, view, actor, recipient, **kwargs):
    data = {
        "to_user": recipient.username,
        "subject": "Hello",
        "message": "Hello there",
        "send_message": "Start Conversation",
    }

    with application.test_request_context(method="POST", data=data):
        login_user(actor)
        response = view(**kwargs)
        messages = get_flashed_messages(with_categories=True)
        logout_user()

    return response, messages


def test_new_conversation_over_the_quota_is_not_sent(
    application, default_settings, no_csrf, no_quota, user, admin_user
):
    response, messages = _send(
        application, views.NewConversation.as_view("new_conversation"), user, admin_user
    )

    assert response.status_code == 302
    assert QUOTA_EXCEEDED in messages
    assert Conversation.count() == 0


def test_draft_over_the_quota_is_not_sent(
    application, default_settings, no_csrf, no_quota, conversation_msgs, user, admin_user
):
    conversation_msgs.draft = True
    conversation_msgs.save()

    response, messages = _send(
        application,
        views.EditConversation.as_view("edit_conversation"),
        user,
        admin_user,
        conversation_id=conversation_msgs.id,
    )

    assert response.status_code == 302
    assert QUOTA_EXCEEDED in messages
    assert conversation_msgs.draft
    # sending would have put a copy into the recipient's inbox
    assert Conversation.count() == 1


def test_disabled_quota_allows_sending_over_the_limit(
    application, default_settings, no_csrf, user, admin_user, monkeypatch
):
    monkeypatch.setattr(
        views,
        "flaskbb_config",
        {"CONVERSATIONS_MESSAGE_QUOTA_ENABLED": False, "CONVERSATIONS_MESSAGE_QUOTA": 0},
    )

    _response, messages = _send(
        application, views.NewConversation.as_view("new_conversation"), user, admin_user
    )

    assert QUOTA_EXCEEDED not in messages
    assert Conversation.count() == 2


def test_recipient_field_opts_into_the_user_lookup(application):
    with application.test_request_context():
        field = ConversationForm(meta={"csrf": False}).to_user()

    assert "data-user-lookup" in field
    assert 'autocomplete="off"' in field
