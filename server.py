# -*- coding: utf-8 -*-
from __future__ import annotations
import threading
import logging
import os
import time
import uvicorn

from app.bot import build_application
from app.webhooks import create_app
from app.config import PORT, JIRA_BASE_URL, PROJECT_KEY, DEPARTMENT_FIELD_ID

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("it_registry.server")
log.info(
    "Start: JIRA_BASE_URL=%s, PROJECT_KEY=%s, DEPARTMENT_FIELD_ID=%s",
    JIRA_BASE_URL, PROJECT_KEY, DEPARTMENT_FIELD_ID
)

def run_api(app):
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")

def main():
    tg_app = build_application()
    fastapi_app = create_app(tg_app)

    t = threading.Thread(target=run_api, args=(fastapi_app,), daemon=True)
    t.start()

    # allow disabling telegram polling for diagnostics
    if os.getenv("DISABLE_TG", "").strip() == "1":
        log.warning("Telegram polling disabled by DISABLE_TG=1, API stays up")
        while True:
            time.sleep(60)

    # resilient polling loop so container does not crash on network hiccups
    while True:
        try:
            log.info("Starting Telegram polling...")
            tg_app.run_polling(close_loop=False)
        except Exception as e:
            log.exception("Polling crashed: %s. Retrying in 10s...", e)
            time.sleep(10)

if __name__ == "__main__":
    main()
