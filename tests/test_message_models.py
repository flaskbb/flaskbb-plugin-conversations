from conversations.models import Message
from conversations.utils import get_latest_messages


def test_conversation_save(conversation):
    """also tests message.save() since we must create a message to save"""
    message = Message(
        user_id=conversation.user_id,
        conversation_id=conversation.id,
        message="Hello World",
    )
    conversation.save(message=message)
    assert conversation.shared_id is not None


def test_first_message(conversation_msgs, user):
    conversation = conversation_msgs
    assert conversation.first_message.message == "First message"


def test_last_message(conversation_msgs, user):
    conversation = conversation_msgs
    assert conversation.last_message.message == "Second message"

    message = Message(user_id=user.id, message="Third message")
    conversation.save(message=message)
    assert conversation.last_message.message != "Second message"


def test_delete_user_with_conversations(conversation_msgs, user):
    assert user.delete()


def test_latest_messages_are_plain_rows(conversation_msgs, user, admin_user):
    conversation_msgs.unread = True
    conversation_msgs.save()

    latest = get_latest_messages(user.id)

    assert len(latest) == 1
    assert latest[0].id == conversation_msgs.id
    assert latest[0].subject == conversation_msgs.subject
    assert latest[0].from_username == user.username
    assert latest[0].last_message_at == conversation_msgs.last_message.date_created
    assert get_latest_messages(admin_user.id) == []
