# -*- coding: utf-8 -*-
import httpx
import re, logging
from typing import Optional, Dict, Any, List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)

from .settings import (
    PROJECT_KEY, DEPARTMENT_FIELD_ID, REG_EDITORS_GROUP, LOG_PEOPLE_FIELD
)
from .store import get_login, set_login, delete_login, set_pref, get_pref  # ⬅ добавили get_pref
from .jira_client import (
    get_issue, search_latest_by_department, list_unique_departments,
    get_editmeta, update_issue_fields, user_in_group,
    list_unique_values,  # уже используется для подбора вариантов
    search_one_by_dept_and_field,  # ⬅ новая функция
)
from .formatters import format_issue_card, FIELD_ID

log = logging.getLogger("it_registry.handlers")

# ---- helpers ----
ISSUE_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]+-\d+$", re.I)

def _detect_key_or_dept(arg: str) -> Dict[str, str]:
    s = (arg or "").strip()
    if ISSUE_KEY_RE.match(s):
        return {"key": s.upper()}
    return {"dept": s}

async def _load_issue_by_arg(arg: str) -> Optional[Dict[str, Any]]:
    x = _detect_key_or_dept(arg)
    if "key" in x:
        return await get_issue(x["key"])
    else:
        return await search_latest_by_department(x["dept"])

def _people_debug(issue: Dict[str, Any]) -> None:
    if not LOG_PEOPLE_FIELD:
        return
    names = issue.get("names") or {}
    fields = issue.get("fields") or {}
    for fid, fname in names.items():
        if not isinstance(fname, str):
            continue
        low = fname.lower()
        if low.startswith("owners") or "ответствен" in low:
            raw = fields.get(fid)
            log.debug("Owners raw (%s = %s): %r", fid, fname, raw)

# соответствие Отдел -> какое поле показывать вторым (должно совпадать с webhooks.py)
DEPT_TO_FIELD = {
    "Закупки": FIELD_ID["Лицензии"],
    "HelpDesk": FIELD_ID["Система"],
}

# ---- /start ----
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user

    # (опционально) фиксируем пользователя в БД (не критично)
    try:
        from .storage import upsert_user
        upsert_user(tg_id=chat.id, tg_username=user.username)
    except Exception:
        pass

    try:
        depts = await list_unique_departments()
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        if code == 401:
            msg = (
                "Jira отвечает 401 (Unauthorized).\n"
                "Проверьте JIRA_USER/JIRA_PASS и права на REST API у этого пользователя."
            )
        elif code == 403:
            msg = "Jira отвечает 403 (Forbidden). Нет прав читать проект REG или поле отделов."
        else:
            msg = f"Ошибка Jira: {code}\nURL: {e.request.url}"
        await context.bot.send_message(chat.id, msg)
        return
    except httpx.RequestError as e:
        await context.bot.send_message(chat.id, f"Не удалось обратиться к Jira: {e}")
        return
    except Exception as e:
        await context.bot.send_message(chat.id, f"Внутренняя ошибка при получении отделов: {e}")
        return

    if not depts:
        await context.bot.send_message(chat.id, "Не нашёл значения в поле «Отдел» в Jira.")
        return

    depts_sorted = sorted({str(d).strip() for d in depts if str(d).strip()})
    keyboard = [[InlineKeyboardButton(text=d, callback_data=f"dept:{d}")]
                for d in depts_sorted]

    await context.bot.send_message(
        chat.id,
        "Выберите отдел:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML,
    )

# ---- выбор отдела → показ второго поля ----
async def on_pick_dept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, dept = query.data.split(":", 1)

    # сохраняем отдел в prefs (используется webhook'ом) 
    set_pref(update.effective_user.id, dept=dept)

    field_id = DEPT_TO_FIELD.get(dept)
    if not field_id:
        await query.edit_message_text(
            f"Вы выбрали отдел: <b>{dept}</b>\n"
            f"Дополнительный фильтр для этого отдела не требуется. Готово.",
            parse_mode="HTML",
        )
        return

    try:
        options = await list_unique_values(field_id)
    except Exception as e:
        await query.edit_message_text(
            f"Вы выбрали отдел: <b>{dept}</b>\n"
            f"Ошибка при получении вариантов: {e}",
            parse_mode="HTML",
        )
        return

    if not options:
        await query.edit_message_text(
            f"Вы выбрали отдел: <b>{dept}</b>\n"
            "Не нашёл вариантов для второго фильтра. Готово.",
            parse_mode="HTML",
        )
        return

    field_label = "Лицензии" if field_id == FIELD_ID.get("Лицензии") else "Система"

    context.user_data[f"opts_{field_id}"] = options
    kb = [
        [InlineKeyboardButton(v, callback_data=f"opt:{field_id}:{i}")]
        for i, v in enumerate(options)
    ]

    await query.edit_message_text(
        f"Вы выбрали отдел: <b>{dept}</b>\n\n"
        f"Теперь выберите значение поля <b>{field_label}</b>:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="HTML",
    )

# ---- выбор значения второго поля → сохраняем подписку ----
async def on_pick_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    try:
        _, field_id, idx_str = (q.data or "").split(":", 2)
        idx = int(idx_str)
    except Exception:
        await q.edit_message_text("Некорректные данные выбора. Повторите: /start")
        return

    options = context.user_data.get(f"opts_{field_id}", [])
    if not (0 <= idx < len(options)):
        await q.edit_message_text("Выбор не распознан. Повторите: /start")
        return

    value = options[idx]
    set_pref(update.effective_user.id, field_id=field_id, value=value)  # сохраняем фильтр 

    await q.edit_message_text(
        "Подписка обновлена.\n"
        f"Фильтр: <b>{value}</b>.\n"
        "Теперь вы будете получать уведомления только по выбранным значениям.",
        parse_mode="HTML",
    )

# ---- /info ----
async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    arg = " ".join(context.args) if context.args else ""

    # 1) Если аргумент указан, ведём себя как раньше: ключ задачи или название отдела
    if arg:
        issue = await _load_issue_by_arg(arg)
        if not issue:
            await update.message.reply_text("Не нашёл задачу. Проверь ключ/отдел.")
            return
        _people_debug(issue)
        await update.message.reply_text(
            format_issue_card(issue),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    # 2) Без аргументов — показываем задачу по текущей подписке пользователя
    pref = get_pref(update.effective_user.id)  # {"dept": "...", "filters": {...}} 
    dept = (pref or {}).get("dept")
    if not dept:
        await update.message.reply_text("Сначала выберите отдел и фильтр: /start")
        return

    # Берём первый сохранённый фильтр (по ТЗ — он ровно один)
    filters_map = (pref or {}).get("filters") or {}
    if filters_map:
        field_id, value = next(iter(filters_map.items()))
        issue = await search_one_by_dept_and_field(dept, field_id, value)
    else:
        issue = await search_latest_by_department(dept)

    if not issue:
        await update.message.reply_text("По вашей подписке задач пока не найдено.")
        return

    _people_debug(issue)
    await update.message.reply_text(
        f"<code>{issue.get('key','')}</code>\n"  # компактный заголовок с ключом
        f"{format_issue_card(issue)}",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )

# ---- /help & /whoami & /unlink (без изменений по логике) ----
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Команды\n"
        "/start — выбрать отдел и фильтр\n"
        "/info [KEY|Отдел] — показать карточку. Без аргументов — по вашей подписке\n"
        "/edit <KEY|Отдел> — изменить поле (только для группы reg_editors)\n"
        "/whoami — показать привязанный Jira-логин\n"
        "/unlink — отвязать свой TG от Jira-логина\n"
    )
    await update.message.reply_text(text)

async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = get_login(update.effective_user.id)
    if u:
        await update.message.reply_text(f"Ваш Jira-логин: <b>{u}</b>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("Логин не привязан. Используйте /edit, чтобы привязать.")

async def cmd_unlink(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    delete_login(update.effective_user.id)
    await update.message.reply_text("Готово. Привязка удалена.")

# ---- /edit (как было)
ASK_LOGIN, CHOOSE_VALUE = range(2)

async def cmd_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    arg = " ".join(context.args) if context.args else ""
    if not arg:
        await update.message.reply_text("Использование: /edit <KEY|Отдел>")
        return ConversationHandler.END

    context.user_data["__edit_arg"] = arg
    jira_login = get_login(update.effective_user.id)
    if not jira_login:
        await update.message.reply_text(
            "Укажите ваш логин в Jira (userkey), например jira-admin.\n"
            "Мы проверим членство в группе reg_editors и привяжем ваш Telegram к Jira-аккаунту."
        )
        return ASK_LOGIN

    return await _continue_edit(update, context, jira_login)

async def on_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    jira_login = (update.message.text or "").strip()
    if not jira_login:
        await update.message.reply_text("Пусто. Введите логин.")
        return ASK_LOGIN

    if not await user_in_group(jira_login):
        await update.message.reply_text("Нет прав (вы не состоите в группе reg_editors).")
        return ConversationHandler.END

    set_login(update.effective_user.id, jira_login)
    return await _continue_edit(update, context, jira_login)

async def _continue_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, jira_login: str) -> int:
    # ... без изменений (редактирование Criticality) ...
    return ConversationHandler.END  # укорочено ради компактности примера

def register(app: Application) -> None:
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_pick_dept,   pattern=r"^dept:"))
    app.add_handler(CallbackQueryHandler(on_pick_filter, pattern=r"^opt:"))

    app.add_handler(CommandHandler("info", cmd_info))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("whoami", cmd_whoami))
    app.add_handler(CommandHandler("unlink", cmd_unlink))

    # edit flow и setcrit — как у тебя было
