from __future__ import annotations

from typing import Any

from coboose.catalog import Catalog, Workspace


def match_workspaces(
    catalog: Catalog, issue: dict[str, Any]
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for workspace in catalog.workspaces:
        score, reasons = score_workspace(workspace, issue)
        scored.append(
            {
                "id": workspace.id,
                "name": workspace.name,
                "description": workspace.description,
                "folders": catalog.workspace_repo_names(workspace),
                "fallback": workspace.fallback,
                "score": score,
                "reasons": reasons,
            }
        )
    scored.sort(key=lambda item: (item["score"], item["fallback"]), reverse=True)
    return scored


def recommend_workspace(
    catalog: Catalog, issue: dict[str, Any]
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    ranked = match_workspaces(catalog, issue)
    if not ranked:
        return None, []
    winner = ranked[0]
    if winner["score"] == 0:
        fallback = next((item for item in ranked if item["fallback"]), None)
        if fallback:
            fallback = dict(fallback)
            fallback["reasons"] = fallback["reasons"] + ["fallback workspace"]
            others = [item for item in ranked if item["id"] != fallback["id"]]
            return fallback, others
    return winner, ranked[1:]


def score_workspace(workspace: Workspace, issue: dict[str, Any]) -> tuple[int, list[str]]:
    match = workspace.match
    score = 0
    reasons: list[str] = []

    project = _project_key(issue)
    if project and _contains(match.projects, project):
        score += 5
        reasons.append(f"project {project}")

    issue_type = issue.get("issue_type") or ""
    if issue_type and _contains(match.issue_types, issue_type):
        score += 3
        reasons.append(f"issue type {issue_type}")

    for component in issue.get("components") or []:
        if _contains(match.components, component):
            score += 4
            reasons.append(f"component {component}")

    for label in issue.get("labels") or []:
        if _contains(match.labels, label):
            score += 3
            reasons.append(f"label {label}")

    haystack_summary = (issue.get("summary") or "").lower()
    haystack_description = (issue.get("description") or "").lower()
    for keyword in match.keywords:
        needle = keyword.lower()
        if needle and needle in haystack_summary:
            score += 2
            reasons.append(f"summary keyword '{keyword}'")
        elif needle and needle in haystack_description:
            score += 1
            reasons.append(f"description keyword '{keyword}'")

    return score, reasons


def _project_key(issue: dict[str, Any]) -> str:
    project = issue.get("project")
    if isinstance(project, dict):
        return str(project.get("key") or "")
    return str(project or "")


def _contains(values: list[str], candidate: str) -> bool:
    wanted = {item.lower() for item in values}
    return candidate.lower() in wanted
