# -*- coding: utf-8 -*-
"""
conversations.views
~~~~~~~~~~~~~~~~~~~

This module contains the forms for the
conversations Plugin.

:copyright: (c) 2018 by Peter Justin.
:license: BSD License, see LICENSE for more details.
"""

import logging
from uuid import UUID

from flask_babelplus import lazy_gettext as _
from flask_login import current_user
from flask_wtf import FlaskForm
from flaskbb.user.models import User
from wtforms import Field, StringField, SubmitField, TextAreaField, ValidationError
from wtforms.validators import DataRequired

from .models import Conversation, Message

logger = logging.getLogger(__name__)


class ConversationForm(FlaskForm):
    to_user = StringField(
        _("Recipient"),
        validators=[DataRequired(message=_("A valid username is required."))],
    )

    subject = StringField(
        _("Subject"),
        validators=[DataRequired(message=_("A Subject is required."))],
    )

    message = TextAreaField(
        _("Message"),
        validators=[DataRequired(message=_("A message is required."))],
    )

    send_message = SubmitField(_("Start Conversation"))
    save_message = SubmitField(_("Save Conversation"))

    def validate_to_user(self, field: Field):
        user = User.get_by(username=field.data)
        if not user:
            raise ValidationError(_("The username you entered does not exist."))
        if user.id == current_user.id:
            raise ValidationError(_("You cannot send a PM to yourself."))

    def save(
        self,
        from_user: int,
        to_user: int,
        user_id: int,
        unread: bool,
        as_draft: bool = False,
        shared_id: UUID | None = None,
    ):
        conversation = Conversation(
            subject=self.subject.data,
            draft=as_draft,
            shared_id=shared_id,
            from_user_id=from_user,
            to_user_id=to_user,
            user_id=user_id,
            unread=unread,
        )
        message = Message(message=self.message.data, user_id=from_user)
        return conversation.save(message=message)


class MessageForm(FlaskForm):
    message = TextAreaField(
        _("Message"),
        validators=[DataRequired(message=_("A message is required."))],
    )
    submit = SubmitField(_("Send Message"))

    def save(self, conversation: Conversation, user_id: int, unread: bool = False):
        """Saves the form data to the model.

        :param conversation: The Conversation object.
        :param user_id: The id from the user who sent the message.
        :param reciever: If the message should also be stored in the recievers
                         inbox.
        """
        message = Message(message=self.message.data, user_id=user_id)

        if unread:
            conversation.unread = True
            conversation.save()
        return message.save(conversation)
