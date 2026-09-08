# -*- coding: utf-8 -*-
"""
conversations
~~~~~~~~~~~~~

A conversations Plugin for FlaskBB.

:copyright: (c) 2018 by Peter Justin.
:license: BSD License, see LICENSE for more details.
"""

import os

from flask import Flask
from flask_login import current_user
from flaskbb.settings.definitions import IntSetting, SettingGroup
from flaskbb.forum.models import Post
from flaskbb.user.models import User
from flaskbb.utils.helpers import real, render_template
from pluggy import HookimplMarker

from .utils import get_latest_messages, get_message_count, get_unread_count
from .views import conversations_bp

hookimpl = HookimplMarker("flaskbb")

SETTINGS = SettingGroup(
    key="conversations",
    name="Conversations Settings",
    description="Settings for the conversations plugin.",
    settings=(
        IntSetting(
            key="MESSAGE_QUOTA",
            value=50,
            min=0,
            name="Private Message Quota",
            description="The amount of messages a user can have.",
        ),
    ),
)


@hookimpl
def flaskbb_load_setting_groups():
    return SETTINGS


# connect the hooks
@hookimpl
def flaskbb_load_migrations():
    return os.path.join(os.path.dirname(__file__), "migrations")


@hookimpl
def flaskbb_load_translations():
    return os.path.join(os.path.dirname(__file__), "translations")


@hookimpl
def flaskbb_load_blueprints(app: Flask):
    app.register_blueprint(
        conversations_bp, url_prefix="/conversations", template_dir="templates"
    )


@hookimpl
def flaskbb_current_user(app: Flask, user: User):
    setattr(user, "message_count", get_message_count(user.id))


@hookimpl
def flaskbb_tpl_user_nav_loggedin_before():
    return render_template(
        "_inject_navlink.html",
        unread_messages=get_latest_messages(real(current_user).id),
        unread_count=get_unread_count(real(current_user).id),
    )


@hookimpl(trylast=True)
def flaskbb_tpl_profile_actions(user: User):
    return render_template("_inject_new_message_button.html", user=user)


@hookimpl(trylast=True)
def flaskbb_tpl_post_author_info_after(user: User, post: Post):
    return render_template("_inject_new_message_link.html", user=user, post=post)
