from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence

from harness import HarnessError, __version__
from harness.catalog import catalog_to_dict, load_catalog
from harness.clone import clone_repos
from harness.doctor import run_doctor
from harness.jira_client import JiraClient, jira_settings_from_env, parse_issue_key
from harness.output import render
from harness.paths import find_harness_root, load_dotenv_files
from harness.prepare import prepare_issue
from harness.routing import recommend_workspace
from harness.workspace import generate_workspaces, list_workspaces, open_workspace


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        payload = dispatch(args)
        if payload is not None:
            print(render(payload, args.format))
        return 0
    except HarnessError as exc:
        _print_error(exc.message, getattr(args, "format", "json"), getattr(exc, "payload", None))
        return exc.code
    except KeyboardInterrupt:
        _print_error("Interrupted", getattr(args, "format", "json"))
        return 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harness",
        description=(
            "Clone sibling git repos, query Jira Cloud with basic auth, "
            "and select a feature VS Code workspace."
        ),
    )
    parser.add_argument("--version", action="version", version=f"harness {__version__}")
    parser.add_argument(
        "--format",
        choices=("json", "markdown", "text"),
        default="json",
        help="Stdout format. Copilot should keep json.",
    )
    parser.add_argument("--catalog", type=Path, help="Override catalog/stack.yaml")
    parser.add_argument("--repos", type=Path, help="Override repositories.yml")
    parser.add_argument("--root", type=Path, help="Override harness root")
    sub = parser.add_subparsers(dest="command", required=True)

    clone = sub.add_parser("clone", help="Clone repositories.yml remotes as siblings of the harness")
    clone.add_argument("--only", help="Comma-separated repository names")
    clone.add_argument("--tag", help="Comma-separated tags from repositories.yml")
    clone.add_argument("--update", action="store_true", help="Fetch and fast-forward existing clones")
    clone.add_argument("--dry-run", action="store_true")
    clone.add_argument("--https", action="store_true", help="Rewrite git@github.com URLs to HTTPS")

    jira = sub.add_parser("jira", help="Jira Cloud commands (basic auth)")
    jira_sub = jira.add_subparsers(dest="jira_command", required=True)
    jira_get = jira_sub.add_parser("get", help="Fetch one issue")
    jira_get.add_argument("issue")
    jira_comments = jira_sub.add_parser("comments", help="Fetch issue comments")
    jira_comments.add_argument("issue")
    jira_search = jira_sub.add_parser("search", help="Run JQL")
    jira_search.add_argument("jql")
    jira_search.add_argument("--max-results", type=int, default=25)
    jira_context = jira_sub.add_parser("context", help="Issue plus comments")
    jira_context.add_argument("issue")
    jira_sub.add_parser("whoami", help="Validate Jira credentials")
    jira_sub.add_parser("schema", help="Show configured Jira output fields")

    workspace = sub.add_parser("workspace", help="Feature workspace helpers")
    workspace_sub = workspace.add_subparsers(dest="workspace_command", required=True)
    workspace_sub.add_parser("list", help="List feature workspaces")
    workspace_sub.add_parser("generate", help="Write .code-workspace files from the catalog")
    workspace_match = workspace_sub.add_parser("match", help="Recommend a workspace for an issue")
    workspace_match.add_argument("issue")
    workspace_open = workspace_sub.add_parser("open", help="Open a workspace in VS Code")
    workspace_open.add_argument("id")
    workspace_path = workspace_sub.add_parser("path", help="Print a workspace file path")
    workspace_path.add_argument("id")

    prepare = sub.add_parser(
        "prepare",
        help="Fetch a ticket, choose a workspace, and report missing repos",
    )
    prepare.add_argument("issue")
    prepare.add_argument(
        "--clone-missing",
        action="store_true",
        help="Clone repos required by the matched workspace",
    )
    prepare.add_argument(
        "--no-generate",
        action="store_true",
        help="Do not regenerate workspace files",
    )

    doctor = sub.add_parser("doctor", help="Check catalog, clones, and Jira configuration")
    doctor.add_argument("--ping-jira", action="store_true")

    sub.add_parser("catalog", help="Show the resolved catalog")
    sub.add_parser("repos", help="Show the repositories.yml manifest")
    return parser


def dispatch(args: argparse.Namespace) -> Any:
    harness_root = Path(args.root).resolve() if args.root else find_harness_root()
    load_dotenv_files(harness_root)
    catalog = load_catalog(
        harness_root,
        stack_path=Path(args.catalog).resolve() if args.catalog else None,
        repos_path=Path(args.repos).resolve() if args.repos else None,
    )

    if args.command == "clone":
        only = _split_ids(args.only)
        tags = _split_ids(getattr(args, "tag", None))
        repos = clone_repos(
            catalog,
            harness_root,
            only=only,
            tags=tags,
            update=args.update,
            dry_run=args.dry_run,
            https=args.https,
        )
        payload = {
            "sibling_root": str(catalog.sibling_root(harness_root)),
            "repos": repos,
        }
        if any(item.get("action") == "blocked" for item in repos):
            raise _payload_error(
                "One or more repo URLs are still placeholders. Update repositories.yml.",
                payload,
            )
        return payload
    if args.command == "jira":
        return _dispatch_jira(args, catalog)
    if args.command == "workspace":
        return _dispatch_workspace(args, catalog, harness_root)
    if args.command == "prepare":
        return prepare_issue(
            catalog,
            harness_root,
            _client(),
            args.issue,
            clone_missing=args.clone_missing,
            generate=not args.no_generate,
        )
    if args.command == "doctor":
        payload = run_doctor(catalog, harness_root, ping_jira=args.ping_jira)
        if not payload.get("ok"):
            raise _payload_error("Doctor found blocking issues.", payload)
        return payload
    if args.command == "catalog":
        return catalog_to_dict(catalog, harness_root)
    if args.command == "repos":
        payload = catalog_to_dict(catalog, harness_root)
        return {
            "manifest": payload["repos_source"],
            "parent_dir": payload["parent_dir"],
            "sibling_root": payload["sibling_root"],
            "repositories": payload["repos"],
        }
    raise HarnessError(f"Unknown command: {args.command}")


def _dispatch_jira(args: argparse.Namespace, catalog: Any) -> Any:
    settings = catalog.jira
    if args.jira_command == "schema":
        return {"jira": settings.schema()}
    client = _client()
    if args.jira_command == "get":
        return client.get_issue(args.issue, settings=settings)
    if args.jira_command == "comments":
        if not settings.wants("comments"):
            raise HarnessError("Comments are disabled in catalog/stack.yaml jira.fields")
        return {
            "key": parse_issue_key(args.issue),
            "comments": client.get_comments(args.issue, max_results=settings.max_comments),
        }
    if args.jira_command == "search":
        return {"jql": args.jql, "issues": client.search(args.jql, max_results=args.max_results)}
    if args.jira_command == "context":
        return client.get_context(args.issue, settings=settings)
    if args.jira_command == "whoami":
        return client.myself()
    raise HarnessError(f"Unknown jira command: {args.jira_command}")


def _dispatch_workspace(args: argparse.Namespace, catalog: Any, harness_root: Path) -> Any:
    if args.workspace_command == "list":
        return {"workspaces": list_workspaces(catalog, harness_root)}
    if args.workspace_command == "generate":
        return {"workspaces": generate_workspaces(catalog, harness_root)}
    if args.workspace_command == "match":
        issue = _client().get_issue(args.issue, settings=catalog.jira)
        recommended, alternatives = recommend_workspace(catalog, issue)
        return {
            "issue": {
                "key": issue.get("key"),
                "summary": issue.get("summary"),
                "project": issue.get("project"),
                "components": issue.get("components"),
                "labels": issue.get("labels"),
            },
            "recommended": recommended,
            "alternatives": alternatives,
        }
    if args.workspace_command == "open":
        return open_workspace(catalog.workspace_file(harness_root, args.id))
    if args.workspace_command == "path":
        path = catalog.workspace_file(harness_root, args.id)
        return {"id": args.id, "file": str(path), "exists": path.exists()}
    raise HarnessError(f"Unknown workspace command: {args.workspace_command}")


def _client() -> JiraClient:
    base_url, email, token = jira_settings_from_env()
    return JiraClient(base_url, email, token)


def _split_ids(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _payload_error(message: str, payload: dict) -> HarnessError:
    return HarnessError(message, payload=payload)


def _print_error(message: str, fmt: str, payload: dict | None = None) -> None:
    body = {"error": message}
    if payload:
        body.update(payload)
    if fmt == "json":
        print(render(body, "json"), file=sys.stderr)
    else:
        print(message, file=sys.stderr)
        if payload:
            print(render(payload, fmt), file=sys.stderr)


