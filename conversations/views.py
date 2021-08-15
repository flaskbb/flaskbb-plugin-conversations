# -*- coding: utf-8 -*-
"""
    conversations.views
    ~~~~~~~~~~~~~~~~~~~

    This module contains the views for the
    conversations Plugin.

    :copyright: (c) 2018 by Peter Justin.
    :license: BSD License, see LICENSE for more details.
"""
import logging
import uuid
from functools import wraps

from flask import Blueprint, abort, flash, redirect, request, url_for
from flask.views import MethodView
from flask_babelplus import gettext as _
from flask_login import current_user, login_required

from flaskbb.extensions import db
from flaskbb.user.models import User
from flaskbb.utils.helpers import (
    format_quote,
    real,
    register_view,
    render_template,
)
from flaskbb.utils.settings import flaskbb_config

from .forms import ConversationForm, MessageForm
from .models import Conversation, Message
from .utils import get_message_count, invalidate_cache


logger = logging.getLogger(__name__)

conversations_bp = Blueprint(
    "conversations_bp", __name__, template_folder="templates"
)


def check_message_box_space(redirect_to=None):
    """Checks the message quota has been exceeded. If thats the case
    it flashes a message and redirects back to some endpoint.

    :param redirect_to: The endpoint to redirect to. If set to ``None`` it
                        will redirect to the ``conversations_bp.inbox``
                        endpoint.
    """
    if get_message_count(current_user) >= flaskbb_config["MESSAGE_QUOTA"]:
        flash(
            _(
                "You cannot send any messages anymore because you have "
                "reached your message limit."
            ),
            "danger",
        )
        return redirect(redirect_to or url_for("conversations_bp.inbox"))


def require_message_box_space(f):
    """Decorator for :func:`check_message_box_space`."""
    # not sure how this can be done without explicitly providing a decorator
    # for this
    @wraps(f)
    def wrapper(*a, **k):
        return check_message_box_space() or f(*a, **k)

    return wrapper


class Inbox(MethodView):
    decorators = [login_required]

    def get(self):
        page = request.args.get("page", 1, type=int)
        # the inbox will display both, the recieved and the sent messages
        conversations = (
            Conversation.query.filter(
                Conversation.user_id == current_user.id,
                Conversation.trash == False,
            )
            .order_by(Conversation.date_modified.desc())
            .paginate(page, flaskbb_config["TOPICS_PER_PAGE"], False)
        )

        return render_template("inbox.html", conversations=conversations)


class ViewConversation(MethodView):
    decorators = [login_required]
    form = MessageForm

    def get(self, conversation_id):
        conversation = Conversation.query.filter_by(
            id=conversation_id, user_id=current_user.id
        ).first_or_404()

        if conversation.unread:
            conversation.unread = False
            invalidate_cache(current_user)
            conversation.save()

        form = self.form()
        return render_template(
            "conversation.html", conversation=conversation, form=form
        )

    @require_message_box_space
    def post(self, conversation_id):
        conversation = Conversation.query.filter_by(
            id=conversation_id, user_id=current_user.id
        ).first_or_404()

        form = self.form()
        if form.validate_on_submit():
            to_user_id = None
            # If the current_user is the user who recieved the message
            # then we have to change the id's a bit.
            if current_user.id == conversation.to_user_id:
                to_user_id = conversation.from_user_id
                to_user = conversation.from_user
            else:
                to_user_id = conversation.to_user_id
                to_user = conversation.to_user

            form.save(conversation=conversation, user_id=current_user.id)

            # save the message in the recievers conversation
            old_conv = conversation
            conversation = Conversation.query.filter(
                Conversation.user_id == to_user_id,
                Conversation.shared_id == conversation.shared_id,
            ).first()

            # user deleted the conversation, start a new conversation with just
            # the recieving message
            if conversation is None:
                conversation = Conversation(
                    subject=old_conv.subject,
                    from_user=real(current_user),
                    to_user=to_user,
                    user_id=to_user_id,
                    shared_id=old_conv.shared_id,
                )
                conversation.save()

            form.save(
                conversation=conversation, user_id=current_user.id, unread=True
            )
            invalidate_cache(conversation.to_user)

            return redirect(
                url_for(
                    "conversations_bp.view_conversation",
                    conversation_id=old_conv.id,
                )
            )

        return render_template(
            "conversation.html", conversation=conversation, form=form
        )


class NewConversation(MethodView):
    decorators = [login_required]
    form = ConversationForm

    def get(self):
        form = self.form()
        form.to_user.data = request.args.get("to_user")
        return render_template(
            "message_form.html", form=form, title=_("Compose Message")
        )

    def post(self):
        form = self.form()
        if form.validate_on_submit():
            check_message_box_space()

            to_user = User.query.filter_by(username=form.to_user.data).first()

            # this is the shared id between conversations because the messages
            # are saved on both ends
            shared_id = uuid.uuid4()

            # Save the message in the current users inbox
            form.save(
                from_user=current_user.id,
                to_user=to_user.id,
                user_id=current_user.id,
                unread=False,
                shared_id=shared_id,
            )

            # Save the message in the recievers inbox
            form.save(
                from_user=current_user.id,
                to_user=to_user.id,
                user_id=to_user.id,
                unread=True,
                shared_id=shared_id,
            )
            invalidate_cache(to_user)

            flash(_("Message sent."), "success")
            return redirect(url_for("conversations_bp.sent"))

        return render_template(
            "message_form.html", form=form, title=_("Compose Message")
        )


class RawMessage(MethodView):
    decorators = [login_required]

    def get(self, message_id):

        message = Message.query.filter_by(id=message_id).first_or_404()

        # abort if the message was not the current_user's one or the one of the
        # recieved ones
        if not (
            message.conversation.from_user_id == current_user.id
            or message.conversation.to_user_id == current_user.id
        ):
            abort(404)

        return format_quote(
            username=message.user.username, content=message.message
        )


class ArchiveConversation(MethodView):
    decorators = [login_required]

    def post(self, conversation_id):
        conversation = Conversation.query.filter_by(
            id=conversation_id, user_id=current_user.id
        ).first_or_404()

        conversation.trash = True
        conversation.save()

        return redirect(url_for("conversations_bp.inbox"))


class UnarchiveConversation(MethodView):
    decorators = [login_required]

    def post(self, conversation_id):
        conversation = Conversation.query.filter_by(
            id=conversation_id, user_id=current_user.id
        ).first_or_404()

        conversation.trash = False
        conversation.save()
        return redirect(url_for("conversations_bp.archived"))


class DeleteConversation(MethodView):
    decorators = [login_required]

    def post(self, conversation_id):
        conversation = Conversation.query.filter_by(
            id=conversation_id, user_id=current_user.id
        ).first_or_404()

        conversation.delete()
        return redirect(url_for("conversations_bp.archived"))


class ArchivedMessages(MethodView):
    decorators = [login_required]

    def get(self):

        page = request.args.get("page", 1, type=int)

        conversations = (
            Conversation.query.filter(
                Conversation.user_id == current_user.id,
                Conversation.trash == True,
            )
            .order_by(Conversation.date_modified.desc())
            .paginate(page, flaskbb_config["TOPICS_PER_PAGE"], False)
        )

        return render_template("archived.html", conversations=conversations)


register_view(
    conversations_bp, routes=["/", "/inbox"], view_func=Inbox.as_view("inbox")
)
register_view(
    conversations_bp,
    routes=["/archived"],
    view_func=ArchivedMessages.as_view("archived"),
)
register_view(
    conversations_bp,
    routes=["/<int:conversation_id>/delete"],
    view_func=DeleteConversation.as_view("delete_conversation"),
)
register_view(
    conversations_bp,
    routes=["/<int:conversation_id>/archive"],
    view_func=ArchiveConversation.as_view("archive_conversation"),
)
register_view(
    conversations_bp,
    routes=["/<int:conversation_id>/unarchive"],
    view_func=UnarchiveConversation.as_view("unarchive_conversation"),
)
register_view(
    conversations_bp,
    routes=["/<int:conversation_id>/view"],
    view_func=ViewConversation.as_view("view_conversation"),
)
register_view(
    conversations_bp,
    routes=["/message/<int:message_id>/raw"],
    view_func=RawMessage.as_view("raw_message"),
)
register_view(
    conversations_bp,
    routes=["/new"],
    view_func=NewConversation.as_view("new_conversation"),
)
