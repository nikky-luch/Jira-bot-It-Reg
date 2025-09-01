# IT Registry Telegram Bot (for Jira Data Center)

This repo contains a working skeleton of a Telegram bot + FastAPI service that:
- lets a user pick their **Department** and see formatted info for a Registry issue (`System Record`) in project `REG`;
- receives **Jira Webhook** events and pushes updates **only** to subscribers of the matching department;
- allows **editing selected fields** for the *Закупки* department with group-based permission checks;
- runs in **Docker** via `docker compose up -d`.

Target: **Jira DC v10.3.6**, ScriptRunner optional. Bot: **python-telegram-bot v20**, **FastAPI**, **Uvicorn**, **SQLAlchemy**.

## Quick start
1. Create Jira service user (e.g., `reg-bot`) with Browse/View/Edit in project `REG`.  
   Create group `reg_editors` for editors (or change in `.env`).
2. Ensure project `REG`, issuetype `System Record`, and field **Отдел** `customfield_10100` (Select).
3. (Recommended) Jira WebHook → URL `http://<bot-host>:8081/jira-webhook`, events Created/Updated, JQL:
   `project = REG AND issuetype = "System Record"`
4. Copy `.env.example` → `.env`, fill tokens/creds/ids.
5. `docker compose up -d`

## Commands
- `/start` — choose department (inline buttons)
- `/dept` — change department
- `/info — show Jira issue
- `/link_jira <username>` — link TG user to Jira login for permissions
- `/edit` — edit mapped fields for your dept (configured for “Закупки”)
- `/help` — this help

## Notes
- Compose v2 — no `version:` key needed.
- No `apt-get` in Dockerfile (builds reliably on Windows/corp networks).
