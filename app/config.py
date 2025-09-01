import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "http://localhost:8080").rstrip("/")
PUBLIC_JIRA_BASE_URL = os.getenv("PUBLIC_JIRA_BASE_URL", "http://localhost:8080").rstrip("/")
JIRA_USERNAME = os.getenv("JIRA_USERNAME", "")
JIRA_PASSWORD = os.getenv("JIRA_PASSWORD", "")
JIRA_VERIFY_SSL = os.getenv("JIRA_VERIFY_SSL", "false").lower() in ("1","true","yes","on")

PROJECT_KEY = os.getenv("PROJECT_KEY", "REG")
DEPARTMENT_FIELD_ID = os.getenv("DEPARTMENT_FIELD_ID", "customfield_10100")
EDITOR_GROUP_GLOBAL = os.getenv("EDITOR_GROUP_GLOBAL", "reg_editors")

PORT = int(os.getenv("PORT", "8081"))

DEPARTMENTS = [
    "HelpDesk",
    "Закупки",
    "Системный анализ",
    "IT-департамент",
    "Проектный офис",
    "Кибербезопасность",
    "Финансовая аналитика",
    "IDM",
    "Корпоративная архитектура",
]

DEPT_FIELD_MAP = {
    "Закупки": {
        "System Code": "customfield_10001",    # Text
        "Support Team": "customfield_10003",   # Select
        "Criticality": "customfield_10004",    # Select
        "Integrations": "customfield_10005",   # Text multi-line
        "URL": "customfield_10006",            # URL
    },
    # сюда позже добавим другие отделы
}


RENDER_ORDER = [
    "Статус",
    "Владельцы",
    "Команда",
    "Критичность",
    "Интеграции",
    "System Code",
    "URL",
]
