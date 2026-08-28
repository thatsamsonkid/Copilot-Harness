from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence

from coboose import CobooseError, __version__
from coboose.bootstrap import bootstrap_project
from coboose.branch import align_branches
from coboose.catalog import catalog_to_dict, load_catalog
from coboose.clone import clone_repos
from coboose.context import collect_context
from coboose.doctor import run_doctor
from coboose.envspec import find_var, list_env, set_env_value, unset_env_value
from coboose.handoff import latest_handoff, list_handoffs, write_handoff
from coboose.jira_client import JiraClient, jira_settings_from_env, parse_issue_key
from coboose.keychain import login_token, logout_token
from coboose.onboard import run_init
from coboose.output import render
from coboose.paths import find_coboose_root, load_dotenv_files
from coboose.prepare import prepare_issue
from coboose.prompt import PromptSession
from coboose.routing import recommend_workspace
from coboose.start import collect_start_plan, execute_start_env, execute_start_run
from coboose.status import collect_status
from coboose.templates import get_template, template_to_dict, templates_payload
from coboose.workspace import generate_workspaces, list_workspaces, open_workspace
from coboose.workspace_create import create_workspace
from coboose.workspace_detect import current_workspace_payload, resolve_workspace_scope

JIRA_MINE_JQL = "assignee = currentUser() AND resolution = EMPTY ORDER BY updated DESC"


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    raw = list(argv) if argv is not None else sys.argv[1:]
    args = parser.parse_args(raw)
    _apply_leading_globals(args, raw)
    try:
        payload = dispatch(args)
        if payload is not None:
            print(render(payload, args.format))
        return 0
    except CobooseError as exc:
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
    shared.add_argument("--root", type=Path, help="Override Coboose repo root")
    return shared


def build_parser() -> argparse.ArgumentParser:
    shared = _shared_options()
    parser = argparse.ArgumentParser(
        prog="coboose",
        description=(
            "Clone product git repos under parent_dir, bootstrap projects from "
            "listed templates, query Jira Cloud with basic auth, inspect clone "
            "git status, and create or select a feature VS Code workspace."
        ),
        parents=[shared],
    )
    parser.add_argument("--version", action="version", version=f"coboose {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    clone = sub.add_parser(
        "clone",
        parents=[shared],
        help="Clone repositories.yml remotes under parent_dir (outside this Coboose repo)",
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
    jira_mine = jira_sub.add_parser(
        "mine",
        parents=[shared],
        help="List unresolved issues assigned to the current Jira user",
    )
    jira_mine.add_argument("--max-results", type=int, default=15)
    jira_sub.add_parser("whoami", parents=[shared], help="Validate Jira credentials")
    jira_sub.add_parser("schema", parents=[shared], help="Show configured Jira output fields")
    jira_login = jira_sub.add_parser(
        "login",
        parents=[shared],
        help="Store the Jira API token in macOS Keychain or Windows Credential Manager",
    )
    jira_login.add_argument(
        "--from-env",
        action="store_true",
        help="Move JIRA_API_TOKEN from .env into the OS keychain, then blank .env",
    )
    jira_login.add_argument(
        "--keep-env",
        action="store_true",
        help="Leave JIRA_API_TOKEN in .env after storing it in the keychain",
    )
    jira_logout = jira_sub.add_parser(
        "logout",
        parents=[shared],
        help="Remove the Jira API token from the OS keychain",
    )
    jira_logout.add_argument(
        "--clear-env",
        action="store_true",
        help="Also blank JIRA_API_TOKEN in .env",
    )

    env = sub.add_parser(
        "env",
        parents=[shared],
        help="List or store catalog/env.yaml variables (secrets go in the OS keychain)",
    )
    env_sub = env.add_subparsers(dest="env_command", required=True)
    env_list = env_sub.add_parser(
        "list",
        parents=[shared],
        help="Show declared env vars and whether each is present (never prints values)",
    )
    env_list.add_argument(
        "--workspace",
        help="Limit to shared vars plus names scoped to this workspace id",
    )
    env_list.add_argument(
        "--all",
        dest="all_repos",
        action="store_true",
        help="List every catalog/env.yaml name (ignore the open workspace)",
    )
    env_set = env_sub.add_parser(
        "set",
        parents=[shared],
        help="Set one declared variable. Secrets are stored in the OS keychain.",
    )
    env_set.add_argument("name", help="Variable name from catalog/env.yaml")
    env_set.add_argument(
        "--from-env",
        action="store_true",
        help="Read the current value from .env / the environment, then store it",
    )
    env_set.add_argument(
        "--keep-env",
        action="store_true",
        help="Leave a secret in .env after storing it in the keychain",
    )
    env_unset = env_sub.add_parser(
        "unset",
        parents=[shared],
        help="Remove a secret from the OS keychain",
    )
    env_unset.add_argument("name", help="Variable name from catalog/env.yaml")
    env_unset.add_argument(
        "--clear-env",
        action="store_true",
        help="Also blank the variable in .env",
    )

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
        "--include-coboose",
        dest="include_coboose",
        action="store_true",
        default=None,
        help="Add this Coboose repo as the first workspace folder (default)",
    )
    workspace_create.add_argument(
        "--no-include-coboose",
        dest="include_coboose",
        action="store_false",
        help="Do not add this Coboose repo as a workspace folder",
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
    workspace_current = workspace_sub.add_parser(
        "current",
        parents=[shared],
        help="Detect the open feature workspace (COBOOSE_WORKSPACE / workspace file)",
    )
    workspace_current.add_argument(
        "--file",
        dest="workspace_file",
        type=Path,
        help="Read the workspace id from a .code-workspace file",
    )

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
    _add_scope_flags(doctor)

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
    _add_scope_flags(context)

    status = sub.add_parser(
        "status",
        parents=[shared],
        help="Read-only git snapshot of sibling clones (branch, dirty, ahead/behind)",
    )
    status.add_argument("--repo", help="Comma-separated repository names")
    _add_scope_flags(status)

    branch = sub.add_parser(
        "branch",
        parents=[shared],
        help="Suggest or create the same Jira-key branch in matched sibling clones",
    )
    branch.add_argument("issue", help="Jira issue key or browse URL")
    branch.add_argument("--repo", help="Comma-separated repository names")
    _add_scope_flags(branch)
    branch.add_argument(
        "--create",
        action="store_true",
        help="Create or checkout the branch in clean clones",
    )
    branch.add_argument("--dry-run", action="store_true")

    handoff = sub.add_parser(
        "handoff",
        parents=[shared],
        help="Write or read a session note under handoffs/ (gitignored)",
    )
    handoff_sub = handoff.add_subparsers(dest="handoff_command", required=True)
    handoff_write = handoff_sub.add_parser(
        "write", parents=[shared], help="Write a session note with the current sibling snapshot"
    )
    handoff_write.add_argument("--issue", help="Jira issue key to tag the note")
    handoff_write.add_argument("--note", help="What the next chat should resume")
    _add_scope_flags(handoff_write)
    handoff_sub.add_parser("list", parents=[shared], help="List handoff notes")
    handoff_sub.add_parser("latest", parents=[shared], help="Show the newest handoff note")

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
    start.add_argument(
        "--all",
        dest="all_repos",
        action="store_true",
        help="Plan every enabled repo (ignore the open workspace)",
    )
    start.add_argument("--repo", help="Comma-separated repository names")
    start.add_argument(
        "--save",
        action="store_true",
        help=(
            "Write the current sequence to workspaces/<id>.start.yml "
            "(needs --workspace or COBOOSE_WORKSPACE)"
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
    coboose_root = Path(args.root).resolve() if args.root else find_coboose_root()
    load_dotenv_files(coboose_root)
    catalog = load_catalog(
        coboose_root,
        stack_path=Path(args.catalog).resolve() if args.catalog else None,
        repos_path=Path(args.repos).resolve() if args.repos else None,
        templates_path=Path(args.templates).resolve() if args.templates else None,
    )

    if args.command == "clone":
        only = _split_ids(args.only)
        tags = _split_ids(getattr(args, "tag", None))
        repos = clone_repos(
            catalog,
            coboose_root,
            only=only,
            tags=tags,
            update=args.update,
            dry_run=args.dry_run,
            https=args.https,
        )
        payload = {
            "sibling_root": str(catalog.sibling_root(coboose_root)),
            "repos": repos,
        }
        if any(item.get("action") == "blocked" for item in repos):
            raise _payload_error(
                "One or more repo URLs are still placeholders. Update repositories.yml.",
                payload,
            )
        return payload
    if args.command == "jira":
        return _dispatch_jira(args, catalog, coboose_root)
    if args.command == "env":
        return _dispatch_env(args, catalog, coboose_root)
    if args.command == "workspace":
        return _dispatch_workspace(args, catalog, coboose_root)
    if args.command == "prepare":
        return prepare_issue(
            catalog,
            coboose_root,
            _client(),
            args.issue,
            clone_missing=args.clone_missing,
            generate=not args.no_generate,
        )
    if args.command == "doctor":
        payload = run_doctor(
            catalog,
            coboose_root,
            ping_jira=args.ping_jira,
            workspace_id=args.workspace,
            all_repos=bool(getattr(args, "all_repos", False)),
        )
        if not payload.get("ok"):
            raise _payload_error("Doctor found blocking issues.", payload)
        return payload
    if args.command == "init":
        return run_init(
            catalog,
            coboose_root,
            interactive=args.interactive,
            ping_jira=args.ping_jira,
        )
    if args.command == "context":
        return collect_context(
            catalog,
            coboose_root,
            only=_split_ids(args.repo),
            workspace_id=args.workspace,
            all_repos=bool(args.all_repos),
        )
    if args.command == "status":
        return collect_status(
            catalog,
            coboose_root,
            only=_split_ids(args.repo),
            cwd=Path.cwd(),
            workspace_id=args.workspace,
            all_repos=bool(args.all_repos),
        )
    if args.command == "branch":
        return align_branches(
            catalog,
            coboose_root,
            args.issue,
            only=_split_ids(args.repo),
            create=args.create,
            dry_run=args.dry_run,
            workspace_id=args.workspace,
            all_repos=bool(args.all_repos),
        )
    if args.command == "handoff":
        return _dispatch_handoff(args, catalog, coboose_root)
    if args.command == "start":
        if args.action == "run":
            if args.shell:
                raise CobooseError(
                    "coboose start run starts the app. "
                    "Use `start env --repo <name> --shell` to apply env in a terminal."
                )
            repos = _split_ids(args.repo) or []
            if len(repos) != 1:
                raise CobooseError("coboose start run requires exactly one --repo")
            payload = execute_start_run(
                catalog,
                coboose_root,
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
                raise CobooseError("coboose start env requires exactly one --repo")
            if args.save:
                raise CobooseError("coboose start env does not write a start plan")
            payload = execute_start_env(
                catalog,
                coboose_root,
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
            coboose_root,
            workspace_id=args.workspace,
            only=_split_ids(args.repo),
            save=args.save,
            refresh=args.refresh,
            all_repos=bool(getattr(args, "all_repos", False)),
        )
    if args.command == "catalog":
        return catalog_to_dict(catalog, coboose_root)
    if args.command == "repos":
        payload = catalog_to_dict(catalog, coboose_root)
        return {
            "manifest": payload["repos_source"],
            "parent_dir": payload["parent_dir"],
            "sibling_root": payload["sibling_root"],
            "repositories": payload["repos"],
        }
    if args.command == "templates":
        return _dispatch_templates(args, catalog)
    if args.command == "bootstrap":
        return _dispatch_bootstrap(args, catalog, coboose_root)
    raise CobooseError(f"Unknown command: {args.command}")


def _dispatch_jira(args: argparse.Namespace, catalog: Any, coboose_root: Path) -> Any:
    settings = catalog.jira
    if args.jira_command == "schema":
        return {"jira": settings.schema()}
    if args.jira_command == "login":
        return login_token(
            coboose_root,
            from_env=args.from_env,
            clear_env=not args.keep_env,
        )
    if args.jira_command == "logout":
        return logout_token(coboose_root, clear_env=args.clear_env)
    client = _client()
    if args.jira_command == "get":
        return client.get_issue(args.issue, settings=settings)
    if args.jira_command == "comments":
        if not settings.wants("comments"):
            raise CobooseError("Comments are disabled in catalog/stack.yaml jira.fields")
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
    if args.jira_command == "mine":
        issues = client.search(JIRA_MINE_JQL, max_results=args.max_results)
        return {"jql": JIRA_MINE_JQL, "issues": issues}
    raise CobooseError(f"Unknown jira command: {args.jira_command}")


def _dispatch_env(args: argparse.Namespace, catalog: Any, coboose_root: Path) -> Any:
    if args.env_command == "list":
        scope = resolve_workspace_scope(
            catalog,
            coboose_root,
            workspace_id=args.workspace,
            all_repos=bool(getattr(args, "all_repos", False)),
        )
        extra = catalog.workspace(scope.id).env if scope.id else None
        payload = list_env(
            catalog.env_vars,
            coboose_root,
            workspace_id=scope.id,
            extra_names=extra,
            source=catalog.env_source,
        )
        payload["workspace_scope"] = scope.as_payload()
        return payload
    variable = find_var(catalog.env_vars, args.name)
    if args.env_command == "set":
        return set_env_value(
            variable,
            coboose_root,
            from_env=args.from_env,
            clear_env=not args.keep_env,
        )
    if args.env_command == "unset":
        return unset_env_value(variable, coboose_root, clear_env=args.clear_env)
    raise CobooseError(f"Unknown env command: {args.env_command}")


def _dispatch_workspace(args: argparse.Namespace, catalog: Any, coboose_root: Path) -> Any:
    if args.workspace_command == "list":
        return {"workspaces": list_workspaces(catalog, coboose_root)}
    if args.workspace_command == "generate":
        return {"workspaces": generate_workspaces(catalog, coboose_root)}
    if args.workspace_command == "create":
        prompt = PromptSession(interactive=False if args.no_prompt else None)
        return create_workspace(
            catalog,
            coboose_root,
            workspace_id=args.id,
            name=args.name,
            description=args.description,
            folders=_split_ids(args.projects),
            tags=_split_ids(args.tag),
            include_coboose=args.include_coboose,
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
        return open_workspace(catalog.workspace_file(coboose_root, args.id))
    if args.workspace_command == "path":
        path = catalog.workspace_file(coboose_root, args.id)
        return {"id": args.id, "file": str(path), "exists": path.exists()}
    if args.workspace_command == "current":
        return current_workspace_payload(
            catalog,
            coboose_root,
            workspace_file=getattr(args, "workspace_file", None),
        )
    raise CobooseError(f"Unknown workspace command: {args.workspace_command}")


def _dispatch_handoff(args: argparse.Namespace, catalog: Any, coboose_root: Path) -> Any:
    if args.handoff_command == "list":
        return {"handoffs": list_handoffs(coboose_root)}
    if args.handoff_command == "latest":
        return latest_handoff(coboose_root)
    if args.handoff_command == "write":
        issue = parse_issue_key(args.issue) if args.issue else None
        status = collect_status(
            catalog,
            coboose_root,
            workspace_id=getattr(args, "workspace", None),
            all_repos=bool(getattr(args, "all_repos", False)),
        )
        return write_handoff(
            coboose_root,
            issue=issue,
            note=args.note,
            status=status,
        )
    raise CobooseError(f"Unknown handoff command: {args.handoff_command}")


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


def _dispatch_bootstrap(args: argparse.Namespace, catalog: Any, coboose_root: Path) -> Any:
    template_name = args.template_flag or args.template
    if args.template_flag and args.template and args.template_flag != args.template:
        raise CobooseError("Positional template and --template do not match")
    if not template_name:
        raise CobooseError(
            "Pass a listed template: coboose bootstrap --template <name> --name <folder>"
        )
    return bootstrap_project(
        catalog,
        coboose_root,
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


def _apply_leading_globals(args: argparse.Namespace, argv: list[str]) -> None:
    """Keep `coboose --root X status` working.

    Shared options are on both the top parser and each subparser. argparse
    then overwrites dests such as `root` with the subparser default (None)
    when the flag appears before the subcommand.
    """
    command = getattr(args, "command", None)
    if not command or command not in argv:
        return
    leading = argv[: argv.index(command)]
    if not leading:
        return
    parsed, _ = _shared_options().parse_known_args(leading)
    for key in ("root", "catalog", "repos", "templates"):
        value = getattr(parsed, key, None)
        if value is not None and getattr(args, key, None) is None:
            setattr(args, key, value)
    if "--format" in leading:
        args.format = parsed.format


def _add_scope_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace",
        help="Feature workspace id (overrides COBOOSE_WORKSPACE)",
    )
    parser.add_argument(
        "--all",
        dest="all_repos",
        action="store_true",
        help="Include every enabled repositories.yml repo (ignore the open workspace)",
    )


def _split_ids(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _payload_error(message: str, payload: dict) -> CobooseError:
    return CobooseError(message, payload=payload)


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
