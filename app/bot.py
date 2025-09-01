# -*- coding: utf-8 -*-
from __future__ import annotations

from telegram.ext import ApplicationBuilder
from telegram.request import HTTPXRequest

from .config import TELEGRAM_BOT_TOKEN
from .handlers import register


def build_application():
    # используем HTTPXRequest с явными таймаутами и HTTP/1.1
    request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=60.0,
        write_timeout=60.0,
        pool_timeout=30.0,
        http_version="1.1",
    )

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .request(request)
        .build()
    )

    register(app)
    return app
