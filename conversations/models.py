# -*- coding: utf-8 -*-
"""
    conversations.views
    ~~~~~~~~~~~~~~~~~~~

    The models for the conversations and
    messages are located here.

    :copyright: (c) 2018 by Peter Justin.
    :license: BSD License, see LICENSE for more details.
"""
import logging
import uuid

from flaskbb.extensions import db
from flaskbb.utils.database import CRUDMixin, UTCDateTime
from flaskbb.utils.helpers import time_utcnow
from flaskbb.utils.settings import flaskbb_config

from sqlalchemy_utils import UUIDType

logger = logging.getLogger(__name__)


class Conversation(db.Model, CRUDMixin):
    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    to_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    shared_id = db.Column(UUIDType, nullable=False)
    date_created = db.Column(
        UTCDateTime(timezone=True), default=time_utcnow, nullable=False
    )
    date_modified = db.Column(
        UTCDateTime(timezone=True), default=time_utcnow, nullable=False
    )
    trash = db.Column(db.Boolean, default=False, nullable=False)
    unread = db.Column(db.Boolean, default=False, nullable=False)

    messages = db.relationship(
        "Message",
        lazy="joined",
        backref="conversation",
        primaryjoin="Message.conversation_id == Conversation.id",
        order_by="asc(Message.id)",
        cascade="all, delete-orphan",
    )

    # this is actually the users message box
    user = db.relationship(
        "User",
        lazy="joined",
        backref=db.backref("conversations", lazy="dynamic", passive_deletes=True),
        foreign_keys=[user_id],
    )

    # the user to whom the conversation is addressed
    to_user = db.relationship("User", lazy="joined", foreign_keys=[to_user_id])

    # the user who sent the message
    from_user = db.relationship("User", lazy="joined", foreign_keys=[from_user_id])

    @property
    def first_message(self):
        """Returns the first message object."""
        return self.messages[0]

    @property
    def last_message(self):
        """Returns the last message object."""
        return self.messages[-1]

    @property
    def to_user_url(self):
        if self.to_user:
            return self.to_user.url
        return "#"

    @classmethod
    def get_archived_count(cls, user):
        return cls.query.filter(
            cls.user_id == user.id,
            cls.trash == True,
        ).count()

    @classmethod
    def get_inbox(cls, user, page):
        conversations = (
            cls.query.filter(
                cls.user_id == user.id,
                cls.trash == False,
            )
            .order_by(cls.date_modified.desc())
            .paginate(page, flaskbb_config["TOPICS_PER_PAGE"], False)
        )
        return conversations

    @classmethod
    def get_archived(cls, user, page):
        conversations = (
            cls.query.filter(
                cls.user_id == user.id,
                cls.trash == True,
            )
            .order_by(cls.date_modified.desc())
            .paginate(page, flaskbb_config["TOPICS_PER_PAGE"], False)
        )
        return conversations


    def save(self):
        """Saves a conversation and returns the saved conversation object.

        :param message: If given, it will also save the message for the
                        conversation. It expects a Message object.
        """
        db.session.add(self)
        db.session.commit()
        return self

    @classmethod
    def create(cls, content, current_user, to_user, ):

        # this is the shared id between conversations because the messages
        # are saved on both ends
        shared_id = uuid.uuid4()

        # Save the message in the current users inbox
        conv = cls(
            shared_id=shared_id,
            from_user_id=current_user.id,
            to_user_id=to_user.id,
            user_id=current_user.id,
        )
        Message.create(content=content, user_id=current_user.id, conversation=conv)

        # Save the message in the recievers inbox
        conv_reciever = cls(
            shared_id=shared_id,
            from_user_id=to_user.id,
            to_user_id=current_user.id,
            user_id=to_user.id,
        )
        Message.create(content=content, user_id=to_user.id, conversation=conv_reciever)
        return conv


class Message(db.Model, CRUDMixin):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    # backref: conversation
    conversation_id = db.Column(
        db.Integer,
        db.ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # the user who wrote the message
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    message = db.Column(db.Text, nullable=False)
    date_created = db.Column(
        UTCDateTime(timezone=True), default=time_utcnow, nullable=False
    )

    user = db.relationship("User", lazy="joined")

    def save(self):
        """Saves a message."""
        db.session.add(self)
        db.session.commit()
        return self

    @classmethod
    def create(cls, content, user_id, conversation):
        """Creates a new message.

        :param conversation: The  conversation to which the message
                             belongs to.
        """
        msg = cls(message=content, user_id=user_id)
        conversation.unread = True
        conversation.date_modified = time_utcnow()
        msg.conversation = conversation
        msg.date_created = conversation.date_modified
        return msg.save()
