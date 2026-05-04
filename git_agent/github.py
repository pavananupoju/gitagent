from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Optional, Tuple


GITHUB_API = "https://api.github.com"
USER_AGENT = "git-agent/0.1"


def _request_json(
    method: str,
    url: str,
    token: str,
    body: Optional[dict[str, Any]] = None,
) -> Tuple[int, Any]:
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return resp.status, {}
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(err_body) if err_body.strip() else {}
        except json.JSONDecodeError:
            parsed = {"message": err_body or str(e)}
        return e.code, parsed
    except urllib.error.URLError as e:
        reason = e.reason if isinstance(e.reason, str) else str(e.reason)
        return -1, {"message": reason or str(e)}


def get_login(token: str) -> Tuple[bool, str]:
    status, payload = _request_json("GET", f"{GITHUB_API}/user", token)
    if status != 200 or not isinstance(payload, dict):
        msg = payload.get("message", "Unknown error") if isinstance(payload, dict) else str(payload)
        return False, msg
    login = payload.get("login", "")
    if not login:
        return False, "Missing login in API response"
    return True, login


def create_user_repository(
    token: str,
    name: str,
    private: bool = False,
) -> Tuple[bool, str, Optional[str]]:
    """
    Create a repo for the authenticated user.
    Returns (ok, message_or_error, clone_url).
    """
    body = {"name": name, "private": private, "auto_init": False}
    status, payload = _request_json("POST", f"{GITHUB_API}/user/repos", token, body)

    if status == 201 and isinstance(payload, dict):
        clone_url = payload.get("clone_url") or payload.get("ssh_url")
        html = payload.get("html_url", "")
        if clone_url:
            return True, html or clone_url, clone_url
        return False, "Repository created but no clone URL in response", None

    if isinstance(payload, dict):
        msg = payload.get("message", str(payload))
        errors = payload.get("errors")
        if errors:
            msg = f"{msg}: {errors}"
        return False, msg, None

    return False, str(payload), None


def slugify_repo_name(folder_name: str) -> str:
    """GitHub repo names: alphanumeric, ., -, _"""
    s = folder_name.strip()
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-_.")
    if not s:
        s = "repository"
    return s[:100]
