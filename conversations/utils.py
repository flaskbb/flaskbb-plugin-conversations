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
from sqlalchemy import select
from sqlalchemy.sql.operators import and_

from .models import Conversation, Message

MAX_LATEST_CONVERSATIONS = 5


@cache.memoize()
def get_unread_count(user_id: int | None):
    """Returns the unread message count for the given user.

    :param user: The user object.
    """
    return Conversation.count(
        clause=[and_(Conversation.unread.is_(True), Conversation.user_id == user_id)]
    )


@cache.memoize()
def get_message_count(user_id: int | None):
    """Returns the number of private messages of the given user.

    :param user: The user object.
    """
    result = Conversation.count(
        clause=[
            and_(
                Conversation.user_id == user_id,
                Conversation.id == Message.conversation_id,
            ),
        ]
    )
    return result


@cache.memoize()
def get_latest_messages(user_id: int | None):
    """Returns all unread messages for the given user.

    :param user: The user object.
    """
    stmt = (
        select(Conversation)
        .where(Conversation.unread.is_(True), Conversation.user_id == user_id)
        .order_by(Conversation.id.desc())
        .limit(MAX_LATEST_CONVERSATIONS)
    )
    result = db.session.execute(stmt).scalars()
    return list(result)


def invalidate_cache(user_id: int | None):
    """Invalidates the cache."""
    cache.delete_memoized(get_message_count, user_id)
    cache.delete_memoized(get_unread_count, user_id)
    cache.delete_memoized(get_latest_messages, user_id)
