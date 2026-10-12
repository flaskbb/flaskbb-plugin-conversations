"""
conversations.utils
~~~~~~~~~~~~~~~~~~~

This module contains some utils which are used by the
conversations Plugin.

:copyright: (c) 2018 by Peter Justin.
:license: BSD License, see LICENSE for more details.
"""

import datetime
from typing import NamedTuple

from flaskbb.extensions import cache, db
from flaskbb.user.models import User
from sqlalchemy import select
from sqlalchemy.sql.operators import and_

from .models import Conversation, Message

MAX_LATEST_CONVERSATIONS = 5


class LatestConversation(NamedTuple):
    id: int
    subject: str | None
    from_username: str | None
    last_message_at: datetime.datetime


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
def get_latest_messages(user_id: int | None) -> list[LatestConversation]:
    """Returns the latest unread conversations of the given user, as plain
    rows. Loading ``Conversation`` objects would joined-load four ``User``
    relationships per conversation, and every loaded ``User`` fires the
    eager loads other plugins hang on it (e.g. the ranks plugin).
    """
    last_message_at = (
        select(Message.date_created)
        .where(Message.conversation_id == Conversation.id)
        .order_by(Message.id.desc())
        .limit(1)
        .scalar_subquery()
    )
    stmt = (
        select(Conversation.id, Conversation.subject, User.username, last_message_at)
        .outerjoin(User, User.id == Conversation.from_user_id)
        .where(Conversation.unread.is_(True), Conversation.user_id == user_id)
        .order_by(Conversation.id.desc())
        .limit(MAX_LATEST_CONVERSATIONS)
    )
    return [LatestConversation(*row) for row in db.session.execute(stmt)]


def invalidate_cache(user_id: int | None):
    """Invalidates the cache."""
    cache.delete_memoized(get_message_count, user_id)
    cache.delete_memoized(get_unread_count, user_id)
    cache.delete_memoized(get_latest_messages, user_id)
