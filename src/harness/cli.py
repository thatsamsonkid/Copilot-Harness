from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence

from harness import HarnessError, __version__
from harness.bootstrap import bootstrap_project
from harness.catalog import catalog_to_dict, load_catalog
from harness.clone import clone_repos
from harness.context import collect_context
from harness.doctor import run_doctor
from harness.jira_client import JiraClient, jira_settings_from_env, parse_issue_key
from harness.onboard import run_init
from harness.output import render
from harness.paths import find_harness_root, load_dotenv_files
from harness.prepare import prepare_issue
from harness.prompt import PromptSession
from harness.routing import recommend_workspace
from harness.start import collect_start_plan, execute_start_env, execute_start_run
from harness.templates import get_template, template_to_dict, templates_payload
from harness.workspace import generate_workspaces, list_workspaces, open_workspace
from harness.workspace_create import create_workspace


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


def _shared_options() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--format",
        choices=("json", "markdown", "text"),
        default="json",
        help="Stdout format. Copilot should keep json.",
    )
    shared.add_argument("--catalog", type=Path, help="Override catalog/stack.yaml")
    shared.add_argument("--repos", type=Path, help="Override repositories.yml")
    shared.add_argument("--templates", type=Path, help="Override templates.yml")
    shared.add_argument("--root", type=Path, help="Override harness root")
    return shared


def build_parser() -> argparse.ArgumentParser:
    shared = _shared_options()
    parser = argparse.ArgumentParser(
        prog="harness",
        description=(
            "Clone product git repos, bootstrap projects from listed templates, "
            "query Jira Cloud with basic auth, and create or select a feature "
            "VS Code workspace."
        ),
        parents=[shared],
    )
    parser.add_argument("--version", action="version", version=f"harness {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    clone = sub.add_parser(
        "clone",
        parents=[shared],
        help="Clone repositories.yml remotes under parent_dir (outside this harness)",
    )
    clone.add_argument("--only", help="Comma-separated repository names")
    clone.add_argument("--tag", help="Comma-separated tags from repositories.yml")
    clone.add_argument("--update", action="store_true", help="Fetch and fast-forward existing clones")
    clone.add_argument("--dry-run", action="store_true")
    clone.add_argument("--https", action="store_true", help="Rewrite git@github.com URLs to HTTPS")

    jira = sub.add_parser("jira", parents=[shared], help="Jira Cloud commands (basic auth)")
    jira_sub = jira.add_subparsers(dest="jira_command", required=True)
    jira_get = jira_sub.add_parser("get", parents=[shared], help="Fetch one issue")
    jira_get.add_argument("issue")
    jira_comments = jira_sub.add_parser(
        "comments", parents=[shared], help="Fetch issue comments"
    )
    jira_comments.add_argument("issue")
    jira_search = jira_sub.add_parser("search", parents=[shared], help="Run JQL")
    jira_search.add_argument("jql")
    jira_search.add_argument("--max-results", type=int, default=25)
    jira_context = jira_sub.add_parser(
        "context", parents=[shared], help="Issue plus comments"
    )
    jira_context.add_argument("issue")
    jira_sub.add_parser("whoami", parents=[shared], help="Validate Jira credentials")
    jira_sub.add_parser("schema", parents=[shared], help="Show configured Jira output fields")

    workspace = sub.add_parser(
        "workspace", parents=[shared], help="Feature workspace helpers"
    )
    workspace_sub = workspace.add_subparsers(dest="workspace_command", required=True)
    workspace_sub.add_parser(
        "list", parents=[shared], help="List feature workspaces"
    )
    workspace_sub.add_parser(
        "generate", parents=[shared], help="Write .code-workspace files from the catalog"
    )
    workspace_create = workspace_sub.add_parser(
        "create",
        parents=[shared],
        help="Create a feature workspace and pick projects from repositories.yml",
    )
    workspace_create.add_argument(
        "id",
        nargs="?",
        help="Workspace slug. Prompted when omitted in a terminal.",
    )
    workspace_create.add_argument("--name", help="Display name (defaults to a title-cased id)")
    workspace_create.add_argument("--description", help="Short description")
    workspace_create.add_argument(
        "--projects",
        "--folders",
        dest="projects",
        help="Comma-separated repository names from repositories.yml",
    )
    workspace_create.add_argument(
        "--tag",
        help="Comma-separated tags; include every matching repositories.yml entry",
    )
    workspace_create.add_argument(
        "--personal",
        dest="personal",
        action="store_true",
        default=None,
        help=(
            "Create a local-only workspace under workspaces/personal/ "
            "(gitignored). Does not edit catalog/stack.yaml"
        ),
    )
    workspace_create.add_argument(
        "--shared",
        dest="personal",
        action="store_false",
        help=(
            "Add the workspace to catalog/stack.yaml and workspaces/ "
            "for everyone (default)"
        ),
    )
    workspace_create.add_argument(
        "--include-harness",
        dest="include_harness",
        action="store_true",
        default=None,
        help="Add this harness as the first workspace folder (default)",
    )
    workspace_create.add_argument(
        "--no-include-harness",
        dest="include_harness",
        action="store_false",
        help="Do not add this harness as a workspace folder",
    )
    workspace_create.add_argument(
        "--fallback",
        action="store_true",
        help="Use this workspace when no other Jira match scores",
    )
    workspace_create.add_argument("--match-projects", help="Jira project keys for routing")
    workspace_create.add_argument("--match-components", help="Jira components for routing")
    workspace_create.add_argument("--match-labels", help="Jira labels for routing")
    workspace_create.add_argument("--keywords", help="Summary keywords for routing")
    workspace_create.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing workspace with the same id",
    )
    workspace_create.add_argument(
        "--no-generate",
        action="store_true",
        help="Update catalog/stack.yaml only; do not write the .code-workspace file",
    )
    workspace_create.add_argument("--dry-run", action="store_true")
    workspace_create.add_argument(
        "--no-prompt",
        action="store_true",
        help="Do not prompt; require --id and --projects or --tag",
    )
    workspace_match = workspace_sub.add_parser(
        "match", parents=[shared], help="Recommend a workspace for an issue"
    )
    workspace_match.add_argument("issue")
    workspace_open = workspace_sub.add_parser(
        "open", parents=[shared], help="Open a workspace in VS Code"
    )
    workspace_open.add_argument("id")
    workspace_path = workspace_sub.add_parser(
        "path", parents=[shared], help="Print a workspace file path"
    )
    workspace_path.add_argument("id")

    prepare = sub.add_parser(
        "prepare",
        parents=[shared],
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

    doctor = sub.add_parser(
        "doctor",
        parents=[shared],
        help="Check catalog, clones, and Jira configuration",
    )
    doctor.add_argument("--ping-jira", action="store_true")

    init = sub.add_parser(
        "init",
        parents=[shared],
        help="First-run checklist for .env, Jira token, and repository setup",
    )
    init.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt in the terminal for missing Jira values (never use this in chat)",
    )
    init.add_argument("--ping-jira", action="store_true")

    context = sub.add_parser(
        "context",
        parents=[shared],
        help="Discover Graphify graphs, instruction files, and verify commands in sibling repos",
    )
    context.add_argument("--repo", help="Comma-separated repository names")

    start = sub.add_parser(
        "start",
        parents=[shared],
        help=(
            "Print a workspace start plan, or run one repo without leaking "
            "launch env. Prefer a saved workspaces/<id>.start.yml when present"
        ),
    )
    start.add_argument(
        "action",
        nargs="?",
        choices=("run", "env"),
        help=(
            "Omit for a plan. `run` starts one repo with launch.json env "
            "loaded in-process. `env` applies that repo's env (keys only "
            "on stdout; `--shell` execs a terminal that has the values)"
        ),
    )
    start.add_argument("--workspace", help="Limit the plan to a catalog workspace id")
    start.add_argument("--repo", help="Comma-separated repository names")
    start.add_argument(
        "--save",
        action="store_true",
        help=(
            "Write the current sequence to workspaces/<id>.start.yml "
            "(requires --workspace)"
        ),
    )
    start.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore a saved workspace plan and rediscover from sibling clones",
    )
    start.add_argument(
        "--configuration",
        help="launch.json configuration name for `start run`",
    )
    start.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "For `start run`, print the redacted exec_command, arg counts, "
            "and env keys without launching. For `start env --shell`, "
            "preview keys only"
        ),
    )
    start.add_argument(
        "--shell",
        action="store_true",
        help=(
            "For `start env`, exec an interactive shell with that repo's "
            "launch env applied. Values are not printed"
        ),
    )
    start.add_argument(
        "--prefix",
        help=(
            "Optional prefix for applied launch keys (example: BACKEND). "
            "Default is none so apps see the same names as VS Code. "
            "A trailing underscore is added if missing"
        ),
    )
    start.add_argument(
        "--keep-existing",
        action="store_true",
        help=(
            "Do not overwrite env keys already set in this terminal. "
            "Collisions are reported as skipped_keys"
        ),
    )

    templates = sub.add_parser(
        "templates",
        parents=[shared],
        help="List starter template repositories from templates.yml",
    )
    templates.add_argument(
        "name",
        nargs="?",
        help="Show one listed template (omit to list all)",
    )
    templates.add_argument("--tag", help="Comma-separated tags to filter templates")

    bootstrap = sub.add_parser(
        "bootstrap",
        parents=[shared],
        help="Clone a listed template as a new project under parent_dir",
    )
    bootstrap.add_argument(
        "template",
        nargs="?",
        help="Template name from templates.yml",
    )
    bootstrap.add_argument(
        "--template",
        dest="template_flag",
        help="Template name (same as the positional argument)",
    )
    bootstrap.add_argument(
        "--name",
        help="Project id or destination under parent_dir (frontend/shop-web)",
    )
    bootstrap.add_argument(
        "--group",
        help="Organize the clone under parent_dir/<group>/<name> (frontend, backend, …)",
    )
    bootstrap.add_argument(
        "--register",
        action="store_true",
        help="Append the new project to repositories.yml",
    )
    bootstrap.add_argument(
        "--remote",
        help="Set origin on the new project (and use it when --register is set)",
    )
    bootstrap.add_argument(
        "--tags",
        help="Tags to store when registering in repositories.yml",
    )
    bootstrap.add_argument(
        "--fresh-git",
        action="store_true",
        help="Replace template history with a single bootstrap commit",
    )
    bootstrap.add_argument(
        "--keep-remote",
        action="store_true",
        help="Leave origin pointing at the template repository",
    )
    bootstrap.add_argument("--https", action="store_true", help="Rewrite git@github.com URLs to HTTPS")
    bootstrap.add_argument("--dry-run", action="store_true")

    sub.add_parser("catalog", parents=[shared], help="Show the resolved catalog")
    sub.add_parser("repos", parents=[shared], help="Show the repositories.yml manifest")
    return parser


def dispatch(args: argparse.Namespace) -> Any:
    harness_root = Path(args.root).resolve() if args.root else find_harness_root()
    load_dotenv_files(harness_root)
    catalog = load_catalog(
        harness_root,
        stack_path=Path(args.catalog).resolve() if args.catalog else None,
        repos_path=Path(args.repos).resolve() if args.repos else None,
        templates_path=Path(args.templates).resolve() if args.templates else None,
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
    if args.command == "init":
        return run_init(
            catalog,
            harness_root,
            interactive=args.interactive,
            ping_jira=args.ping_jira,
        )
    if args.command == "context":
        return collect_context(
            catalog,
            harness_root,
            only=_split_ids(args.repo),
        )
    if args.command == "start":
        if args.action == "run":
            if args.shell:
                raise HarnessError(
                    "harness start run starts the app. "
                    "Use `start env --repo <name> --shell` to apply env in a terminal."
                )
            repos = _split_ids(args.repo) or []
            if len(repos) != 1:
                raise HarnessError("harness start run requires exactly one --repo")
            payload = execute_start_run(
                catalog,
                harness_root,
                repos[0],
                configuration=args.configuration,
                dry_run=args.dry_run,
                prefix=args.prefix,
                keep_existing=args.keep_existing,
            )
            if args.dry_run:
                return payload
            raise SystemExit(int(payload.get("exit_code") or 0))
        if args.action == "env":
            repos = _split_ids(args.repo) or []
            if len(repos) != 1:
                raise HarnessError("harness start env requires exactly one --repo")
            if args.save:
                raise HarnessError("harness start env does not write a start plan")
            payload = execute_start_env(
                catalog,
                harness_root,
                repos[0],
                configuration=args.configuration,
                prefix=args.prefix,
                keep_existing=args.keep_existing,
                shell=bool(args.shell) and not args.dry_run,
            )
            if args.shell and not args.dry_run:
                raise SystemExit(0)
            return payload
        return collect_start_plan(
            catalog,
            harness_root,
            workspace_id=args.workspace,
            only=_split_ids(args.repo),
            save=args.save,
            refresh=args.refresh,
        )
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
    if args.command == "templates":
        return _dispatch_templates(args, catalog)
    if args.command == "bootstrap":
        return _dispatch_bootstrap(args, catalog, harness_root)
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
    if args.workspace_command == "create":
        prompt = PromptSession(interactive=False if args.no_prompt else None)
        return create_workspace(
            catalog,
            harness_root,
            workspace_id=args.id,
            name=args.name,
            description=args.description,
            folders=_split_ids(args.projects),
            tags=_split_ids(args.tag),
            include_harness=args.include_harness,
            personal=args.personal,
            fallback=args.fallback,
            match_projects=_split_ids(args.match_projects),
            match_components=_split_ids(args.match_components),
            match_labels=_split_ids(args.match_labels),
            match_keywords=_split_ids(args.keywords),
            force=args.force,
            generate=not args.no_generate,
            dry_run=args.dry_run,
            prompt=prompt,
        )
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


def _dispatch_templates(args: argparse.Namespace, catalog: Any) -> Any:
    source = catalog.templates_source
    if args.name:
        template = get_template(catalog.templates, args.name)
        return {
            "manifest": str(source) if source else None,
            "template": template_to_dict(template),
        }
    tags = _split_ids(getattr(args, "tag", None))
    return templates_payload(catalog.templates, source or Path("templates.yml"), tags=tags)


def _dispatch_bootstrap(args: argparse.Namespace, catalog: Any, harness_root: Path) -> Any:
    template_name = args.template_flag or args.template
    if args.template_flag and args.template and args.template_flag != args.template:
        raise HarnessError("Positional template and --template do not match")
    if not template_name:
        raise HarnessError(
            "Pass a listed template: harness bootstrap --template <name> --name <folder>"
        )
    return bootstrap_project(
        catalog,
        harness_root,
        template_name=template_name,
        dest_name=args.name,
        group=args.group,
        register=args.register,
        remote=args.remote,
        tags=_split_ids(args.tags),
        fresh_git=args.fresh_git,
        keep_remote=args.keep_remote,
        dry_run=args.dry_run,
        https=args.https,
    )


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
