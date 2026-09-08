# -*- coding: utf-8 -*-
"""
conversations.views
~~~~~~~~~~~~~~~~~~~

The models for the conversations and
messages are located here.

:copyright: (c) 2018 by Peter Justin.
:license: BSD License, see LICENSE for more details.
"""

import datetime
import logging
import uuid
from typing import override

from flaskbb.extensions import db
from flaskbb.user.models import User
from flaskbb.utils.database import BaseModel, UTCDateTime
from flaskbb.utils.helpers import time_utcnow
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

logger = logging.getLogger(__name__)


class Conversation(BaseModel):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    to_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    shared_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_created: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(timezone=True), default=time_utcnow, nullable=False
    )
    date_modified: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(timezone=True), default=time_utcnow, nullable=False
    )
    trash: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    draft: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    unread: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        lazy="joined",
        primaryjoin="Message.conversation_id == Conversation.id",
        order_by="asc(Message.id)",
        cascade="all, delete-orphan",
    )

    # this is actually the users message box
    user: Mapped[User] = relationship(
        "User",
        lazy="joined",
        foreign_keys=[user_id],
    )

    # the user to whom the conversation is addressed
    to_user: Mapped[User] = relationship(
        "User", lazy="joined", foreign_keys=[to_user_id]
    )

    # the user who sent the message
    from_user: Mapped[User] = relationship(
        "User", lazy="joined", foreign_keys=[from_user_id]
    )

    @property
    def first_message(self):
        """Returns the first message object."""
        return self.messages[0]

    @property
    def last_message(self):
        """Returns the last message object."""
        return self.messages[-1]

    @override
    def save(self, message: "Message | None" = None):
        """Saves a conversation and returns the saved conversation object.

        :param message: If given, it will also save the message for the
                        conversation. It expects a Message object.
        """
        if message is not None:
            # create the conversation
            self.date_created = time_utcnow()
            db.session.add(self)
            db.session.commit()

            # create the actual message for the conversation
            message.save(self)
            return self

        self.date_modified = time_utcnow()
        db.session.add(self)
        db.session.commit()
        return self


class Message(BaseModel):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # the user who wrote the message
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_created: Mapped[datetime.datetime] = mapped_column(
        UTCDateTime(timezone=True), default=time_utcnow, nullable=False
    )

    user = relationship("User", lazy="joined")

    conversation = relationship("Conversation", back_populates="messages")

    @override
    def save(self, conversation: Conversation | None = None):
        """Saves a private message.

        :param conversation: The  conversation to which the message
                             belongs to.
        """
        if conversation is not None:
            self.conversation = conversation
            conversation.date_modified = time_utcnow()
            self.date_created = time_utcnow()

        db.session.add(self)
        db.session.commit()
        return self
