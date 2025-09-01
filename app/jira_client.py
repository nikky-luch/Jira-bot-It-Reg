# -*- coding: utf-8 -*-
import logging
from typing import Dict, Any, List, Optional, Set

import httpx
from .settings import (
    JIRA_BASE_URL, JIRA_USER, JIRA_PASS, PROJECT_KEY,
    DEPARTMENT_FIELD_ID, HTTP_TIMEOUT, REG_EDITORS_GROUP, VERIFY_SSL
)

log = logging.getLogger("it_registry.jira")

def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=JIRA_BASE_URL.rstrip("/"),
        auth=(JIRA_USER, JIRA_PASS),
        timeout=HTTP_TIMEOUT,
        verify=VERIFY_SSL,
    )

def _jql_field(field_id_or_name: str) -> str:
    """customfield_10100 -> cf[10100]; 'cf[10100]' — как есть; иначе -> "Имя поля"."""
    if field_id_or_name.startswith("customfield_"):
        num = field_id_or_name.split("_", 1)[1]
        return f"cf[{num}]"
    if field_id_or_name.startswith("cf["):
        return field_id_or_name
    return f"\"{field_id_or_name}\""

# --------------------- базовые операции ---------------------

async def get_issue(key: str) -> Dict[str, Any]:
    async with _client() as c:
        r = await c.get(f"/rest/api/2/issue/{key}", params={"expand": "names"})
        r.raise_for_status()
        return r.json()

async def get_editmeta(key: str) -> Dict[str, Any]:
    async with _client() as c:
        r = await c.get(f"/rest/api/2/issue/{key}/editmeta")
        r.raise_for_status()
        return r.json()

async def update_issue_fields(key: str, fields: Dict[str, Any]) -> None:
    async with _client() as c:
        r = await c.put(f"/rest/api/2/issue/{key}", json={"fields": fields})
        r.raise_for_status()

# --------------------- выборки для бота ---------------------

async def search_latest_by_department(dept: str):
    jf = _jql_field(DEPARTMENT_FIELD_ID)
    # для Select используем '='
    jql = f'project = "{PROJECT_KEY}" AND {jf} = "{dept}" ORDER BY created DESC'
    params = {"jql": jql, "maxResults": 1, "expand": "names"}
    async with _client() as c:
        r = await c.get("/rest/api/2/search", params=params)
        r.raise_for_status()
        data = r.json()
        issues = data.get("issues") or []
        return issues[0] if issues else None

async def list_unique_departments(limit: int = 100_000) -> List[str]:
    """Уникальные значения поля 'Отдел' по проекту (с пагинацией)."""
    seen: Set[str] = set()
    start = 0
    step = 100
    cf_id = DEPARTMENT_FIELD_ID
    async with _client() as c:
        while True:
            r = await c.get("/rest/api/2/search", params={
                "jql": f'project = "{PROJECT_KEY}"',
                "fields": cf_id,
                "startAt": start,
                "maxResults": step,
            })
            r.raise_for_status()
            data = r.json()
            issues = data.get("issues") or []
            if not issues:
                break
            for it in issues:
                v = (it.get("fields") or {}).get(cf_id)
                if isinstance(v, dict):
                    val = v.get("value") or v.get("name")
                else:
                    val = v
                if val:
                    seen.add(str(val))
            start += len(issues)
            total = data.get("total") or 0
            if start >= total or start >= limit:
                break
    return sorted(seen)

async def list_unique_values(field_id: str, limit: int = 100_000) -> List[str]:
    """Уникальные значения любого поля (Select/Text/Dict) по проекту."""
    seen: Set[str] = set()
    start = 0
    step = 100
    async with _client() as c:
        while True:
            r = await c.get("/rest/api/2/search", params={
                "jql": f'project = "{PROJECT_KEY}"',
                "fields": field_id,
                "startAt": start,
                "maxResults": step,
            })
            r.raise_for_status()
            data = r.json()
            issues = data.get("issues") or []
            if not issues:
                break

            for it in issues:
                v = (it.get("fields") or {}).get(field_id)
                if isinstance(v, dict):
                    val = v.get("value") or v.get("name")
                else:
                    val = v
                if val is not None:
                    s = str(val).strip()
                    if s:
                        seen.add(s)

            start += len(issues)
            total = data.get("total") or 0
            if start >= total or start >= limit:
                break
    return sorted(seen, key=lambda s: s.lower())

async def search_one_by_dept_and_field(dept: str, field_id: str, value: str):
    """Одна (последняя) задача по связке Отдел + доп.поле."""
    jf_dept = _jql_field(DEPARTMENT_FIELD_ID)
    jf_extra = _jql_field(field_id)
    jql = (
        f'project = "{PROJECT_KEY}" '
        f'AND {jf_dept} = "{dept}" '
        f'AND {jf_extra} = "{value}" '
        f'ORDER BY created DESC'
    )
    params = {"jql": jql, "maxResults": 1, "expand": "names"}
    async with _client() as c:
        r = await c.get("/rest/api/2/search", params=params)
        r.raise_for_status()
        data = r.json()
        issues = data.get("issues") or []
        return issues[0] if issues else None

# --------------------- доступ/группы ---------------------

async def user_in_group(jira_username: str, group: str = REG_EDITORS_GROUP) -> bool:
    """Проверка членства через просмотр участников группы (с пагинацией)."""
    start = 0
    step = 50
    name_lower = (jira_username or "").lower()
    async with _client() as c:
        while True:
            r = await c.get("/rest/api/2/group/member", params={
                "groupname": group,
                "includeInactiveUsers": "true",
                "startAt": start,
                "maxResults": step,
            })
            if r.status_code == 404:
                log.warning("Group %s not found", group)
                return False
            r.raise_for_status()
            data = r.json()
            for u in data.get("values") or []:
                cand = (u.get("name") or u.get("key") or "").lower()
                if cand and cand == name_lower:
                    return True
            if data.get("isLast") is True:
                break
            start += step
    return False
