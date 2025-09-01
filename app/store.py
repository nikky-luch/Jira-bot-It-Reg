# -*- coding: utf-8 -*-
from __future__ import annotations
import json
import os
import threading
from typing import Dict, Tuple, List, Optional

# Файл для простой персистентности внутри контейнера
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
os.makedirs(DATA_DIR, exist_ok=True)
PREFS_FILE = os.path.join(DATA_DIR, "tg_prefs.json")
LOGINS_FILE = os.path.join(DATA_DIR, "tg_logins.json")

_prefs_lock = threading.RLock()
_logins_lock = threading.RLock()

# prefs: chat_id -> {"dept": "Закупки", "filters": {<field_id>: "<value>"}}
_prefs: Dict[str, Dict] = {}
# logins: chat_id -> "jira-userkey"
_logins: Dict[str, str] = {}

def _load(path: str) -> Dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save(path: str, data: Dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

# загружаем при импорте
_prefs.update(_load(PREFS_FILE))
_logins.update(_load(LOGINS_FILE))

# ---------------------- Публичное API: prefs ---------------------------

def set_pref(chat_id: int, dept: Optional[str] = None,
             field_id: Optional[str] = None, value: Optional[str] = None) -> None:
    """Установить/обновить предпочтения пользователя: отдел и опциональный фильтр."""
    cid = str(chat_id)
    with _prefs_lock:
        rec = _prefs.get(cid, {"dept": None, "filters": {}})
        if dept is not None:
            rec["dept"] = dept
        if field_id is not None:
            rec.setdefault("filters", {})[field_id] = value
        _prefs[cid] = rec
        _save(PREFS_FILE, _prefs)

def get_pref(chat_id: int) -> Dict:
    """Вернуть текущие настройки пользователя (может быть пустым)."""
    with _prefs_lock:
        return dict(_prefs.get(str(chat_id), {}))

def users_by_dept(dept: str) -> List[int]:
    """Все chat_id, подписанные на отдел."""
    with _prefs_lock:
        return [int(cid) for cid, rec in _prefs.items() if rec.get("dept") == dept]

def users_by_dept_and_filter(dept: str, field_id: str, value: str) -> List[int]:
    """Все chat_id, подписанные на отдел и конкретное значение дополнительного фильтра."""
    with _prefs_lock:
        out: List[int] = []
        for cid, rec in _prefs.items():
            if rec.get("dept") != dept:
                continue
            if rec.get("filters", {}).get(field_id) == value:
                out.append(int(cid))
        return out

# ---------------------- Публичное API: logins --------------------------

def set_login(chat_id: int, jira_userkey: str) -> None:
    with _logins_lock:
        _logins[str(chat_id)] = jira_userkey
        _save(LOGINS_FILE, _logins)

def get_login(chat_id: int) -> Optional[str]:
    with _logins_lock:
        return _logins.get(str(chat_id))

def delete_login(chat_id: int) -> None:
    with _logins_lock:
        if str(chat_id) in _logins:
            _logins.pop(str(chat_id), None)
            _save(LOGINS_FILE, _logins)

__all__ = [
    "set_pref", "get_pref",
    "users_by_dept", "users_by_dept_and_filter",
    "set_login", "get_login", "delete_login",
]
