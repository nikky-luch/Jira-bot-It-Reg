# -*- coding: utf-8 -*-
from typing import Any, Dict
import logging
import json
import html

log = logging.getLogger("it_registry.formatters")

# ID поля «Отдел»
DEPARTMENT_FIELD_ID = "customfield_10100"

# Карта: Человекочитаемое имя -> ID кастомного поля в Jira
# (эти ID возьми из своей Jira; здесь — примерные значения)
FIELD_ID: Dict[str, str] = {
    "Лицензии":               "customfield_10201",  # Select
    "Система":                "customfield_10205",  # Select
    "Актуальные скрипты":     "customfield_10208",  # Текст/мультистрока
    "Вендоры":                "customfield_10202",  # Текст/мультистрока
    "Инструкция":             "customfield_10207",  # Текст/мультистрока
    "Контакты поставщиков":   "customfield_10203",  # Текст/мультистрока
    "Ответственные":          "customfield_10204",  # User Picker (multi)
    "Ссылки на документацию": "customfield_10206",  # Текст/мультистрока
}

# Порядок вывода полей в карточке
CARD_FIELDS_ORDER = [
    "Система",
    "Лицензии",
    "Актуальные скрипты",
    "Вендоры",
    "Инструкция",
    "Контакты поставщиков",
    "Ответственные",
    "Ссылки на документацию",
]


def _render_value(raw: Any, field_id: str) -> str:
    """
    Нормализует значение поля для вывода в карточку.
    Для «Ответственные» логируем сырые данные, чтобы видеть реальный формат из Jira.
    """
    if raw is None:
        return ""

    # Отладка формата поля «Ответственные»
    if field_id == FIELD_ID["Ответственные"]:
        try:
            log.info(
                "OWNERS_RAW type=%s value=%s",
                type(raw).__name__,
                json.dumps(raw, ensure_ascii=False)[:2000],
            )
        except Exception as e:
            log.info("OWNERS_RAW cannot_dump type=%s error=%s", type(raw).__name__, e)

    # Списки (мультизначные поля, в т.ч. юзеры)
    if isinstance(raw, list):
        parts = []
        for item in raw:
            if isinstance(item, dict):
                # для user picker пытаемся собрать «Имя (key)»
                dn = item.get("displayName")
                key = item.get("key") or item.get("name") or item.get("accountId")
                if dn or key:
                    parts.append(f"{dn or ''}{(' ('+key+')') if key else ''}".strip())
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))
        return "\n".join([p for p in parts if p])

    # Селекты вида {"value": "..."} или {"name": "..."}
    if isinstance(raw, dict) and ("value" in raw or "name" in raw):
        return raw.get("value") or raw.get("name") or ""

    # Прочие типы (строки/числа и т.д.)
    return str(raw)


def format_issue_card(issue: Dict[str, Any]) -> str:
    """
    Собирает тело карточки (без заголовка и ссылки на KEY).
    Заголовок и ссылка добавляются в handlers/webhooks.
    """
    f = issue.get("fields", {}) or {}
    lines = []

    # Отдел — жирный + подчёркнутый для значения
    dept_obj = f.get(DEPARTMENT_FIELD_ID)
    if isinstance(dept_obj, dict):
        dept_val = dept_obj.get("value") or dept_obj.get("name") or ""
    else:
        dept_val = str(dept_obj or "")
    lines.append(f"<b>Отдел:</b> <u><b>{html.escape(dept_val)}</b></u>")

    # Статус
    status = (f.get("status") or {}).get("name")
    if status:
        lines.append(f"<b>Статус:</b> {html.escape(str(status))}")

    # Остальные поля по заданному порядку
    for label in CARD_FIELDS_ORDER:
        field_id = FIELD_ID.get(label)
        if not field_id:
            continue
        raw = f.get(field_id)
        text = _render_value(raw, field_id)
        if not text:
            continue

        safe_text = html.escape(text)
        if "\n" in text:
            lines.append(f"<b>{html.escape(label)}:</b>\n{safe_text}")
        else:
            lines.append(f"<b>{html.escape(label)}:</b> {safe_text}")

    return "\n".join(lines)
