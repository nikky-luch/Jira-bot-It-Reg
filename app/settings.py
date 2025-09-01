# -*- coding: utf-8 -*-
from os import getenv

# Telegram
TELEGRAM_TOKEN = getenv("TELEGRAM_TOKEN", "")

# Jira
JIRA_BASE_URL     = getenv("JIRA_BASE_URL", "http://host.docker.internal:8080")
JIRA_BROWSE_BASE  = getenv("JIRA_BROWSE_BASE", "http://localhost:8080")
JIRA_USER         = getenv("JIRA_USER", "admin")
JIRA_PASS         = getenv("JIRA_PASS", "admin")
PROJECT_KEY       = getenv("PROJECT_KEY", "REG")
DEPARTMENT_FIELD_ID = getenv("DEPARTMENT_FIELD_ID", "customfield_10100")  # "Отдел"
REG_EDITORS_GROUP = getenv("REG_EDITORS_GROUP", "reg_editors")
VERIFY_SSL = (getenv("JIRA_VERIFY_SSL", "true").lower() not in {"0", "false", "no"})

# Таймауты/прочее
HTTP_TIMEOUT = float(getenv("HTTP_TIMEOUT", "15"))

# Включить подробный лог сырого значения для поля типа "Owners"/"Ответственные"
LOG_PEOPLE_FIELD = True
