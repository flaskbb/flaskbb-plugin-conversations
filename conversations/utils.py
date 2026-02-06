# -*- coding: utf-8 -*-
"""
conversations.utils
~~~~~~~~~~~~~~~~~~~

This module contains some utils which are used by the
conversations Plugin.

:copyright: (c) 2018 by Peter Justin.
:license: BSD License, see LICENSE for more details.
"""

from flaskbb.extensions import cache, db
from flaskbb.user.models import User
from sqlalchemy import select

from .models import Conversation, Message

MAX_LATEST_CONVERSATIONS = 5


@cache.memoize()
def get_unread_count(user: User):
    """Returns the unread message count for the given user.

    :param user: The user object.
    """
    return Conversation.count(
        clause=[Conversation.unread.is_(True), Conversation.user_id == user.id]
    )


@cache.memoize()
def get_message_count(user: User):
    """Returns the number of private messages of the given user.

    :param user: The user object.
    """
    if user is None:
        return None

    return Conversation.count(
        clause=[
            Conversation.user_id == user.id,
            Conversation.id == Message.conversation_id,
        ]
    )


@cache.memoize()
def get_latest_messages(user: User):
    """Returns all unread messages for the given user.

    :param user: The user object.
    """
    stmt = (
        select(Conversation)
        .where(Conversation.unread.is_(True), Conversation.user_id == user.id)
        .order_by(Conversation.id.desc())
        .limit(MAX_LATEST_CONVERSATIONS)
    )
    result = db.session.execute(stmt).scalars()
    return list(result)


def invalidate_cache(user: User):
    """Invalidates the cache."""
    cache.delete_memoized(get_message_count, user)
    cache.delete_memoized(get_unread_count, user)
    cache.delete_memoized(get_latest_messages, user)
