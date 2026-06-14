"""Turn the post-mortem remediation plan into real engineering tickets.

Bridges the gap between *reporting* an incident and *actioning* it. Each
``RemediationActionItem`` becomes a GitHub Issue or Jira issue, complete with
priority labels and a verification checklist, so the on-call engineer leaves the
console with a ready-made work queue instead of a static markdown list.

All network calls degrade gracefully and return a structured result so the UI
can show exactly which tickets were filed (or why one failed).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore


_PRIORITY_LABEL = {
    "immediate": "P0-immediate",
    "short_term": "P1-short-term",
    "long_term": "P2-long-term",
}


@dataclass
class TicketResult:
    action_id: str
    title: str
    ok: bool
    url: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ExportResult:
    provider: str
    created: List[TicketResult] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return sum(1 for t in self.created if t.ok)

    @property
    def failure_count(self) -> int:
        return sum(1 for t in self.created if not t.ok)


def _issue_body(item: Dict[str, Any], incident_ref: str) -> str:
    return (
        f"**Incident:** {incident_ref}\n\n"
        f"**Priority:** {item.get('priority', 'n/a')}  |  "
        f"**Category:** {item.get('category', 'n/a')}\n\n"
        f"**Description**\n{item.get('description', '').strip()}\n\n"
        f"**Owner:** {item.get('owner', 'unassigned')}  |  "
        f"**Estimated effort:** {item.get('estimated_effort', 'n/a')}\n\n"
        f"**Verification**\n- [ ] {item.get('verification_method', 'Confirm remediation complete')}\n\n"
        f"---\n_Filed automatically by NeXtrace ({item.get('action_id', '')})_"
    )


def export_to_github(
    remediation_plan: List[Dict[str, Any]],
    incident_ref: str,
    repo: Optional[str] = None,
    token: Optional[str] = None,
) -> ExportResult:
    """Create one GitHub Issue per remediation item.

    ``repo`` is ``owner/name``; ``token`` needs the ``repo`` scope. Falls back to
    ``GITHUB_REPO`` / ``GITHUB_TOKEN`` env vars.
    """
    repo = repo or os.getenv("GITHUB_REPO", "")
    token = token or os.getenv("GITHUB_TOKEN", "")
    result = ExportResult(provider="github")

    if requests is None:
        result.created.append(TicketResult("", "", False, error="requests not installed"))
        return result
    if not repo or not token or token.startswith("your_"):
        result.created.append(TicketResult("", "", False, error="GITHUB_REPO / GITHUB_TOKEN not configured"))
        return result

    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    for item in remediation_plan:
        labels = ["security-incident", "nextrace"]
        pl = _PRIORITY_LABEL.get(item.get("priority", ""))
        if pl:
            labels.append(pl)
        cat = item.get("category")
        if cat:
            labels.append(cat)
        payload = {
            "title": f"[SEC] {item.get('title', 'Remediation task')}",
            "body": _issue_body(item, incident_ref),
            "labels": labels,
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code in (200, 201):
                result.created.append(
                    TicketResult(item.get("action_id", ""), payload["title"], True,
                                 url=resp.json().get("html_url"))
                )
            else:
                result.created.append(
                    TicketResult(item.get("action_id", ""), payload["title"], False,
                                 error=f"HTTP {resp.status_code}: {resp.text[:160]}")
                )
        except Exception as exc:  # noqa: BLE001
            result.created.append(
                TicketResult(item.get("action_id", ""), payload["title"], False, error=str(exc))
            )
    return result


def export_to_jira(
    remediation_plan: List[Dict[str, Any]],
    incident_ref: str,
    base_url: Optional[str] = None,
    email: Optional[str] = None,
    token: Optional[str] = None,
    project_key: Optional[str] = None,
) -> ExportResult:
    """Create one Jira issue per remediation item via the Jira Cloud REST API."""
    base_url = (base_url or os.getenv("JIRA_BASE_URL", "")).rstrip("/")
    email = email or os.getenv("JIRA_EMAIL", "")
    token = token or os.getenv("JIRA_API_TOKEN", "")
    project_key = project_key or os.getenv("JIRA_PROJECT_KEY", "")
    result = ExportResult(provider="jira")

    if requests is None:
        result.created.append(TicketResult("", "", False, error="requests not installed"))
        return result
    if not all([base_url, email, token, project_key]) or token.startswith("your_"):
        result.created.append(TicketResult("", "", False, error="Jira credentials not configured"))
        return result

    url = f"{base_url}/rest/api/3/issue"
    for item in remediation_plan:
        body_text = _issue_body(item, incident_ref)
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": f"[SEC] {item.get('title', 'Remediation task')}",
                "issuetype": {"name": "Task"},
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {"type": "paragraph",
                         "content": [{"type": "text", "text": body_text}]}
                    ],
                },
            }
        }
        try:
            resp = requests.post(url, json=payload, auth=(email, token), timeout=15)
            if resp.status_code in (200, 201):
                key = resp.json().get("key", "")
                result.created.append(
                    TicketResult(item.get("action_id", ""), payload["fields"]["summary"], True,
                                 url=f"{base_url}/browse/{key}" if key else None)
                )
            else:
                result.created.append(
                    TicketResult(item.get("action_id", ""), payload["fields"]["summary"], False,
                                 error=f"HTTP {resp.status_code}: {resp.text[:160]}")
                )
        except Exception as exc:  # noqa: BLE001
            result.created.append(
                TicketResult(item.get("action_id", ""), payload["fields"]["summary"], False, error=str(exc))
            )
    return result


def remediation_to_markdown(remediation_plan: List[Dict[str, Any]], incident_ref: str) -> str:
    """Offline fallback export: a copy-pasteable markdown checklist."""
    lines = [f"# Remediation Plan — {incident_ref}", ""]
    for item in remediation_plan:
        lines.append(f"## [{item.get('priority', '')}] {item.get('title', '')}")
        lines.append(f"- **Category:** {item.get('category', '')}")
        lines.append(f"- **Owner:** {item.get('owner', '')}")
        lines.append(f"- **Effort:** {item.get('estimated_effort', '')}")
        lines.append(f"- **Description:** {item.get('description', '')}")
        lines.append(f"- [ ] {item.get('verification_method', '')}")
        lines.append("")
    return "\n".join(lines)
