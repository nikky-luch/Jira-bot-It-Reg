# IT-Registry: Telegram Bot + Jira DC

Бот для быстрого доступа к «реестру систем» в **Jira Data Center 10.3.6** (проект `REG`, тип `System Record`) и для рассылки обновлений в Telegram.

- Пользователь выбирает **отдел** (и при необходимости «второй фильтр») и получает отформатированную карточку записи.
- При изменениях записи в Jira приходят **push-уведомления** подписчикам соответствующего отдела/фильтра.
- Для отдела **Закупки** доступно **редактирование** ограниченного набора полей (по группе `reg_editors`).
- Развёртывание: **Docker** (`docker compose up -d`).
- Транспорт Telegram: **long polling** (вебхука Telegram нет). Jira → бот: **FastAPI** вебхук `/jira-webhook`.

---

## Архитектура (коротко)

```
Telegram User
   │  команды (/start, /info, /edit, /whoami, /unlink)
   ▼
Telegram Bot API  ←(polling)→  Бот (python-telegram-bot 20 + FastAPI)
                                  ├─ JiraClient (httpx; REST: /search, /issue, /group/member)
                                  ├─ Webhook /jira-webhook (принимает события из Jira)
                                  ├─ Formatters (HTML карточек)
                                  ├─ Store ($DATA_DIR/tg_prefs.json, $DATA_DIR/tg_logins.json)
                                  └─ Settings (.env)
   ▲
   │  ответы/уведомления
   │
Jira DC (проект REG, System Record)
   └─ ScriptRunner Listener → POST http://<bot-host>:8081/jira-webhook
```

---

## Быстрый старт

1) **Подготовьте Jira**
- Проект `REG`, issuetype `System Record`.
- Поле **Отдел** (`customfield_10100`, Select) и остальные нужные поля.
- Техпользователь (например, `reg-bot`) с правами Browse/View/Edit в проекте `REG`.
- Группа редакторов `reg_editors` (для команды `/edit`).

2) **Настройте вебхук из Jira**
- Listener (ScriptRunner) на события **Issue Created/Updated**,
- URL: `http://<bot-host>:8081/jira-webhook`.

3) **Настройте окружение**
- Скопируйте `.env.example` → `.env` и заполните значения (см. раздел **Переменные окружения**).

4) **Запустите**
```bash
docker compose up -d
# Логи:
docker compose logs -f
```

> Рекомендуется смонтировать том для сохранения пользовательских предпочтений:
> ```yaml
> volumes:
>   - ./data:/app/data
> ```

---

## Переменные окружения (минимум)

> В проекте используются оба файла конфигурации (`config.py` и `settings.py`), поэтому присутствуют две группы ключей. Заполните **те, что вы реально используете** в своей сборке.

**Для Telegram (бот):**
| Ключ | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | токен Telegram-бота (используется `bot.py` через `config.py`) |
| `TELEGRAM_TOKEN` | альтернативное имя токена (используется в `settings.py`, если вы его задействуете) |

**Для Jira и общих настроек:**
| Ключ | Описание |
|---|---|
| `JIRA_BASE_URL` | базовый URL Jira, напр. `http://host.docker.internal:8080` |
| `JIRA_BROWSE_BASE` | публичная база ссылок для карточек, напр. `http://jira.company.local` |
| `JIRA_USER`, `JIRA_PASS` | учётка сервисного пользователя |
| `PROJECT_KEY` | ключ проекта реестра (по умолчанию `REG`) |
| `DEPARTMENT_FIELD_ID` | ID поля «Отдел» (по умолчанию `customfield_10100`) |
| `REG_EDITORS_GROUP` | группа редакторов (по умолчанию `reg_editors`) |
| `JIRA_VERIFY_SSL` | `true/false` — проверять SSL (в тестах можно `false`) |
| `PORT` | порт FastAPI (по умолчанию `8081`) |
| `DATA_DIR` | каталог для локального стора (по умолчанию `/app/data`) |

*Опционально*:  
`JIRA_WEBHOOK_SECRET` — если используете проверку секрета на `/jira-webhook` (заголовок `X-Webhook-Secret`).

---

## Команды бота

- `/start` — выбор отдела (и второго фильтра, если предусмотрен).
- `/info [REG-123]` — показать карточку. Без аргумента ищет **последнюю** запись по сохранённым отделу/фильтру.
- `/link_jira <username>` — привязать ваш TG к логину Jira (нужно для проверки прав).
- `/edit [REG-123]` — изменить разрешённые поля (для отдела **Закупки**; доступно только участникам `reg_editors`).  
- `/whoami` — показать привязанный логин Jira.  
- `/unlink` — отвязать логин Jira.  
- `/help` — краткая справка.

---

## Потоки данных

### `/start`
1. Бот запрашивает из Jira список значений **Отдела**:
   ```
   GET /rest/api/2/search
       ?jql=project="REG"
       &fields=customfield_10100
       &startAt=0&maxResults=100
   ```
2. Отправляет сообщение «Выберите отдел» с inline-клавиатурой.
3. После выбора отдела бот при необходимости запрашивает варианты **второго фильтра** (например, «Лицензии» / «Система») — также через `GET /search` с соответствующим `fields`.
4. Выбранные значения сохраняются локально и используются для `/info` и push-уведомлений.

### `/info`
- **С ключом**:  
  ```
  GET /rest/api/2/issue/REG-123
      ?fields=summary,status,customfield_10100,customfield_10201,customfield_10205,...
      &expand=names
  ```
- **Без ключа** (по сохранённым предпочтениям):  
  ```
  GET /rest/api/2/search
      ?jql=project="REG"
           AND cf[10100]="<Отдел>"
           [AND cf[XXXXX]="<Второй фильтр>"]
           ORDER BY updated DESC
      &maxResults=1
      &expand=names
      &fields=summary,status,customfield_10100,customfield_10201,customfield_10205,...
  ```

### `/edit`
1. Проверка привязки (`/link_jira`) и членства в `reg_editors`:  
   ```
   GET /rest/api/2/group/member
       ?groupname=reg_editors
       &startAt=0&maxResults=50
   ```
2. Определение целевой записи: из аргумента (`/edit REG-123`) или по сохранённым отделу/фильтру (поиск через JQL).
3. Чтение текущего значения поля:  
   ```
   GET /rest/api/2/issue/{KEY}?fields=...&expand=names
   ```
4. Обновление:  
   ```
   PUT /rest/api/2/issue/{KEY}
   Content-Type: application/json
   {
     "fields": {
       "<customfield_id>": {"value": "<новое значение>"}  // для Select
       // либо строка для текстовых полей: "<customfield_id>": "новый текст"
     }
   }
   ```

### Обновления из Jira → Telegram
- ScriptRunner Listener отправляет в бот:
  ```
  POST http://<bot-host>:8081/jira-webhook
  Content-Type: application/json
  {
    "issue": { "key": "REG-123",
               "fields": { "customfield_10100": {"value":"Закупки"} } },
    "webhookEvent": "IssueUpdated"
  }
  ```
- Бот формирует карточку и рассылает уведомления **только** подписчикам, у кого совпали отдел/фильтр.

---

## Локальные хранилища

- `$DATA_DIR/tg_prefs.json` — пользовательские предпочтения (выбранный отдел/фильтр) для подписок и `/info`.
- `$DATA_DIR/tg_logins.json` — привязки Telegram ID ↔ логин Jira (для проверки прав).

Оба — обычные JSON; запись атомарная с блокировкой. Для продакшена рекомендуется вынести в БД.

---

## Пример Listener (ScriptRunner Groovy)

```groovy
import com.atlassian.jira.component.ComponentAccessor
import groovy.json.JsonOutput
import java.net.URL
import java.nio.charset.StandardCharsets

final String BOT_URL = "http://<bot-host>:8081/jira-webhook" // замените на ваш DNS

def cfm = ComponentAccessor.getCustomFieldManager()
def deptCf = cfm.getCustomFieldObject("customfield_10100") // ID поля «Отдел»
def deptVal = issue.getCustomFieldValue(deptCf)
def dept = (deptVal?.hasProperty('value')) ? deptVal.value : (deptVal?.toString())

def payload = [
  issue: [ key: issue.key, fields: [ (deptCf.id): dept ? [value: dept] : null ] ],
  webhookEvent: event?.getClass()?.simpleName ?: "Unknown"
]

def conn = new URL(BOT_URL).openConnection()
conn.setRequestMethod("POST")
conn.setDoOutput(true)
conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8")
// conn.setRequestProperty("X-Webhook-Secret", "<secret>") // если включите проверку
conn.getOutputStream().write(JsonOutput.toJson(payload).getBytes(StandardCharsets.UTF_8))
log.info("IT-Registry: webhook -> ${BOT_URL} responded HTTP " + conn.getResponseCode())
```

---

## Разработка локально

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# запустить FastAPI + polling
python server.py
```

Полезно включить подробные логи (`LOG_LEVEL=DEBUG`) и при необходимости временно `JIRA_VERIFY_SSL=false` в тестовой среде.

---

## Безопасность

- Редактирование — **только** для членов `REG_EDITORS_GROUP` (по умолчанию `reg_editors`).  
- Для продакшена рекомендуется включить проверку `X-Webhook-Secret` на `/jira-webhook`.  
- Держите секреты вне репозитория; используйте `.env`/секрет-менеджер.  
- В проде включайте `JIRA_VERIFY_SSL=true` и используйте доверенный CA.

---

## Лицензия

Внутренний проект. Использование вне компании — по согласованию с владельцем репозитория.
