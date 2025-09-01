# -*- coding: utf-8 -*-
from fastapi import FastAPI, Request
from typing import Any, Dict
import logging

from .formatters import format_issue_card, DEPARTMENT_FIELD_ID, FIELD_ID
from .store import users_by_dept, users_by_dept_and_filter
from .jira_client import get_issue

log = logging.getLogger("it_registry.webhooks")
BROWSE_BASE = "http://localhost:8080/browse"

# DEPT→FILTER поле (должно совпадать с handlers)
DEPT_FILTER_FIELD = {
    "Закупки": FIELD_ID["Лицензии"],
    "HelpDesk": FIELD_ID["Система"],
}

def _extract_dept_and_filter(issue: Dict[str, Any]) -> (str, str, str):
    f = issue.get("fields", {})
    # Отдел
    dept_raw = f.get(DEPARTMENT_FIELD_ID)
    if isinstance(dept_raw, dict):
        dept = dept_raw.get("value") or dept_raw.get("name")
    else:
        dept = dept_raw
    dept = str(dept or "")

    # Второй фильтр (если настроен для отдела)
    field_id = DEPT_FILTER_FIELD.get(dept)
    val = ""
    if field_id:
        v = f.get(field_id)
        if isinstance(v, dict):
            val = v.get("value") or v.get("name") or ""
        else:
            val = str(v or "")
    return dept, field_id or "", val

def create_app(tg_application):
    app = FastAPI()

    @app.post("/jira-webhook")
    async def jira_webhook(req: Request):
        data = await req.json()
        key = (data.get("issue") or {}).get("key")
        if not key:
            return {"ok": True}

        issue = await get_issue(key)
        dept, field_id, value = _extract_dept_and_filter(issue)

        # Кому отправлять
        if field_id and value:
            chat_ids = users_by_dept_and_filter(dept, field_id, value)
        else:
            chat_ids = users_by_dept(dept)

        log.info("Webhook %s dept=%s filter=(%s=%s) -> %s users", key, dept, field_id, value, len(chat_ids))

        header = (
            "⚠️ <i><b>Внимание!</b></i> ⚠️\n"
            "— Внеслись новые корректировки в информационную карту — <u><b>Отдел: "
            f"{dept or '—'}</b></u>.\n\n"
            f"<code>{key}</code>\n{BROWSE_BASE}/{key}\n"
        )
        card = format_issue_card(issue)

        for cid in chat_ids:
            try:
                await tg_application.bot.send_message(cid, f"{header}\n{card}", parse_mode="HTML")
            except Exception as e:
                log.warning("Send fail chat=%s: %s", cid, e)

        return {"ok": True}

    return app
