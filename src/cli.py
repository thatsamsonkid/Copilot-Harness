from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence

from goat import GoatError, __version__
from goat.bruno import (
    collect_bruno_inventory,
    list_bruno_envs,
    list_bruno_requests,
    list_bruno_workflows,
    run_bruno_request,
)
from goat.bootstrap import bootstrap_project
from goat.branch import align_branches
from goat.catalog import catalog_to_dict, load_catalog
from goat.clone import clone_repos
from goat.commands import command_reference
from goat.context import collect_context
from goat.glossary import add_term, collect_glossary
from goat.doctor import run_doctor
from goat.envspec import find_var, list_env, set_env_value, unset_env_value
from goat.figma_client import FigmaClient, figma_token_from_env, figma_var
from goat.handoff import latest_handoff, list_handoffs, write_handoff
from goat.install import install_cli, resolve_install_root, uninstall_cli
from goat.jira_client import JiraClient, jira_settings_from_env, parse_issue_key
from goat.keychain import login_token, logout_token
from goat.onboard import run_init
from goat.output import render
from goat.paths import find_goat_root, load_dotenv_files
from goat.prepare import prepare_issue
from goat.prompt import PromptSession
from goat.routing import recommend_workspace
from goat.skills import lift_skills, list_skills, pull_skills, sync_root_skills
from goat.start import collect_start_plan, execute_start_env, execute_start_run
from goat.status import collect_status
from goat.templates import get_template, template_to_dict, templates_payload
from goat.workspace import (
    check_workspaces,
    generate_workspaces,
    list_workspaces,
    open_workspace,
    workspace_sync_error,
)
from goat.workspace_create import create_menu, create_workspace
from goat.workspace_detect import current_workspace_payload, resolve_workspace_scope
from goat.graph.build import build_graph, load_graph, scan_workspace
from goat.graph.query import explain as explain_graph
from goat.graph.query import neighbors as graph_neighbors
from goat.graph.query import path_between
from goat.graph.validate import validate_graph

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
    except GoatError as exc:
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
    shared.add_argument("--root", type=Path, help="Override Goat repo root")
    return shared


def build_parser() -> argparse.ArgumentParser:
    shared = _shared_options()
    parser = argparse.ArgumentParser(
        prog="goat",
        description=(
            "Clone product git repos under parent_dir, bootstrap projects from "
            "listed templates, query Jira Cloud with basic auth, export Figma "
            "frame images, discover Bruno API collections and wrap bru, inspect "
            "clone git status, look up workplace terms and acronyms, "
            "create or select a feature VS Code workspace, "
            "and lift agent skills into the root workspace for the VS Code "
            "Agents window."
        ),
        parents=[shared],
    )
    parser.add_argument("--version", action="version", version=f"goat {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    commands = sub.add_parser(
        "commands",
        aliases=["help"],
        parents=[shared],
        help="Quick reference of every goat command",
    )
    commands.add_argument(
        "group",
        nargs="?",
        help="Show one group or command (jira, figma, bruno, start, …)",
    )

    clone = sub.add_parser(
        "clone",
        parents=[shared],
        help="Clone repositories.yml remotes under parent_dir (outside this Goat repo)",
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

    figma = sub.add_parser("figma", parents=[shared], help="Figma REST commands (personal access token)")
    figma_sub = figma.add_subparsers(dest="figma_command", required=True)
    figma_images = figma_sub.add_parser(
        "images",
        parents=[shared],
        help="Export rendered frame URLs from the Figma Images API",
    )
    figma_images.add_argument("file", help="Figma file key or https://www.figma.com/design/… URL")
    figma_images.add_argument(
        "--ids",
        help="Comma-separated node ids (12:34). Overrides node-id from a URL",
    )
    figma_images.add_argument(
        "--image-format",
        dest="image_format",
        choices=("png", "jpg", "svg", "pdf"),
        help="Image format (default catalog/stack.yaml figma.default_format)",
    )
    figma_images.add_argument(
        "--scale",
        type=float,
        help="Scale 0.01–4 (default catalog/stack.yaml figma.default_scale)",
    )
    figma_comments = figma_sub.add_parser(
        "comments",
        parents=[shared],
        help="Fetch clipped file comments (optional node filter from the URL)",
    )
    figma_comments.add_argument("file", help="Figma file key or https://www.figma.com/design/… URL")
    figma_comments.add_argument(
        "--ids",
        help="Comma-separated node ids. Overrides node-id from a URL",
    )
    figma_comments.add_argument(
        "--file-comments",
        action="store_true",
        help="Return comments for the whole file even when a node-id is present",
    )
    figma_nodes = figma_sub.add_parser(
        "nodes",
        parents=[shared],
        help="Fetch raw Figma node JSON for a small targeted frame (not a page or file)",
    )
    figma_nodes.add_argument("file", help="Figma file key or https://www.figma.com/design/… URL")
    figma_nodes.add_argument(
        "--ids",
        help="Comma-separated node ids (12:34). Overrides node-id from a URL",
    )
    figma_nodes.add_argument(
        "--depth",
        type=int,
        help="Tree depth 1–max (default catalog/stack.yaml figma.default_depth)",
    )
    figma_sub.add_parser("whoami", parents=[shared], help="Validate Figma credentials")
    figma_sub.add_parser("schema", parents=[shared], help="Show configured Figma output fields")
    figma_login = figma_sub.add_parser(
        "login",
        parents=[shared],
        help="Store the Figma personal access token in macOS Keychain or Windows Credential Manager",
    )
    figma_login.add_argument(
        "--from-env",
        action="store_true",
        help="Move FIGMA_ACCESS_TOKEN from .env into the OS keychain, then blank .env",
    )
    figma_login.add_argument(
        "--keep-env",
        action="store_true",
        help="Leave FIGMA_ACCESS_TOKEN in .env after storing it in the keychain",
    )
    figma_logout = figma_sub.add_parser(
        "logout",
        parents=[shared],
        help="Remove the Figma personal access token from the OS keychain",
    )
    figma_logout.add_argument(
        "--clear-env",
        action="store_true",
        help="Also blank FIGMA_ACCESS_TOKEN in .env",
    )

    bruno = sub.add_parser(
        "bruno",
        parents=[shared],
        help="Discover Bruno collections and wrap the bru CLI",
    )
    bruno_sub = bruno.add_subparsers(dest="bruno_command", required=True)
    bruno_sub.add_parser(
        "collections",
        parents=[shared],
        help="List Bruno repos, collections, services, and workflows",
    )
    bruno_requests = bruno_sub.add_parser(
        "requests",
        parents=[shared],
        help="List Bruno requests (optional collection or request filter)",
    )
    bruno_requests.add_argument(
        "target",
        nargs="?",
        help="Collection id, request id, or relative .bru path",
    )
    bruno_envs = bruno_sub.add_parser(
        "envs",
        parents=[shared],
        help="List Bruno environments and service defaults (names only)",
    )
    bruno_envs.add_argument(
        "target",
        nargs="?",
        help="Collection id to limit environments",
    )
    bruno_workflows = bruno_sub.add_parser(
        "workflows",
        parents=[shared],
        help="List described multi-step Bruno workflows (a plan, not a runner)",
    )
    bruno_workflows.add_argument(
        "name",
        nargs="?",
        help="Workflow id for the full step plan",
    )
    bruno_run = bruno_sub.add_parser(
        "run",
        parents=[shared],
        help="Resolve collection cwd + env, then invoke bru run",
    )
    bruno_run.add_argument(
        "target",
        help="Request id, meta name, or relative .bru path",
    )
    bruno_run.add_argument(
        "--collection",
        help="Disambiguate when two collections share a request name",
    )
    bruno_run.add_argument(
        "--service",
        help="Service id from goat.services.yml or catalog/stack.yaml bruno.services",
    )
    bruno_run.add_argument(
        "--env",
        help="Bruno environment name (default: service env, then bruno.default_env)",
    )
    bruno_run.add_argument(
        "--env-var",
        dest="env_vars",
        action="append",
        help="KEY=value passed to bru (repeatable). Values are redacted on stdout",
    )
    bruno_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved bru command without executing HTTP",
    )
    bruno_sub.add_parser(
        "schema",
        parents=[shared],
        help="Show configured Bruno output fields and the request template",
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
    workspace_generate = workspace_sub.add_parser(
        "generate",
        parents=[shared],
        help="Write .code-workspace files from catalog/stack.yaml",
    )
    workspace_generate.add_argument(
        "--check",
        action="store_true",
        help=(
            "Fail if workspaces/*.code-workspace drift from catalog/stack.yaml; "
            "do not write files"
        ),
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
        "--include-goat",
        "--include-coboose",
        dest="include_goat",
        action="store_true",
        default=None,
        help="Add this Goat repo as the first workspace folder (default)",
    )
    workspace_create.add_argument(
        "--no-include-goat",
        "--no-include-coboose",
        dest="include_goat",
        action="store_false",
        help="Do not add this Goat repo as a workspace folder",
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
        "--menu",
        action="store_true",
        help="Print a compact project picker (no write). Use this from chat.",
    )
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
        help="Detect the open feature workspace (GOAT_WORKSPACE / workspace file)",
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
        help="Check catalog, clones, Jira, optional Figma, and Bruno configuration",
    )
    doctor.add_argument("--ping-jira", action="store_true")
    doctor.add_argument("--ping-figma", action="store_true")
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

    install = sub.add_parser(
        "install",
        parents=[shared],
        help="Register goat on PATH so it runs from any directory",
    )
    _add_install_flags(install)

    uninstall = sub.add_parser(
        "uninstall",
        parents=[shared],
        help="Remove the goat PATH shim written by goat install",
    )
    _add_install_flags(uninstall)

    graph = sub.add_parser(
        "graph",
        parents=[shared],
        help="Canonical workspace graph (extractors → evidence → JSON)",
    )
    graph_sub = graph.add_subparsers(dest="graph_command", required=True)
    graph_scan = graph_sub.add_parser(
        "scan",
        parents=[shared],
        help="Run extractors and report evidence counts (no write)",
    )
    graph_scan.add_argument("--workspace", help="Limit to a catalog workspace id")
    graph_build = graph_sub.add_parser(
        "build",
        parents=[shared],
        help="Correlate extractors and write .workspace/generated/workspace-graph.json",
    )
    graph_build.add_argument("--workspace", help="Limit to a catalog workspace id")
    graph_build.add_argument(
        "--no-write",
        action="store_true",
        help="Build and validate in memory without writing the generated file",
    )
    graph_validate = graph_sub.add_parser(
        "validate",
        parents=[shared],
        help="Validate a workspace-graph.json file",
    )
    graph_validate.add_argument(
        "file",
        nargs="?",
        help="Path to workspace-graph.json (default: .workspace/generated/workspace-graph.json)",
    )
    graph_explain = graph_sub.add_parser(
        "explain",
        parents=[shared],
        help="Show why an edge exists (evidence, classification, confidence)",
    )
    graph_explain.add_argument("source", help="Node id or slug (application:frontend)")
    graph_explain.add_argument(
        "target",
        nargs="?",
        help="Optional second node; explain edges between the two",
    )
    graph_explain.add_argument(
        "--file",
        dest="graph_file",
        help="Graph JSON to read (default: generated workspace-graph.json)",
    )
    graph_neighbors = graph_sub.add_parser(
        "neighbors",
        parents=[shared],
        help="List inbound and outbound edges for one node",
    )
    graph_neighbors.add_argument("node")
    graph_neighbors.add_argument("--file", dest="graph_file")
    graph_path = graph_sub.add_parser(
        "path",
        parents=[shared],
        help="Directed path between two nodes",
    )
    graph_path.add_argument("source")
    graph_path.add_argument("target")
    graph_path.add_argument("--file", dest="graph_file")

    glossary = sub.add_parser(
        "glossary",
        parents=[shared],
        help="Workplace terms and acronyms so Copilot uses the team's language",
    )
    glossary_sub = glossary.add_subparsers(dest="glossary_command", required=True)
    glossary_list = glossary_sub.add_parser(
        "list",
        parents=[shared],
        help="List workplace terms from catalog/glossary.yml and sibling glossaries",
    )
    _add_scope_flags(glossary_list)
    glossary_list.add_argument("--repo", help="Comma-separated repository names")
    glossary_list.add_argument(
        "--kind",
        choices=("acronym", "term"),
        help="Only acronyms or only longer terms",
    )
    glossary_get = glossary_sub.add_parser(
        "get",
        parents=[shared],
        help="Look up one term or alias (suggestions if unmatched)",
    )
    glossary_get.add_argument("term", help="Term or acronym to look up")
    _add_scope_flags(glossary_get)
    glossary_get.add_argument("--repo", help="Comma-separated repository names")
    glossary_search = glossary_sub.add_parser(
        "search",
        parents=[shared],
        help="Search term names, aliases, and meanings",
    )
    glossary_search.add_argument("query", help="Substring to match")
    _add_scope_flags(glossary_search)
    glossary_search.add_argument("--repo", help="Comma-separated repository names")
    glossary_add = glossary_sub.add_parser(
        "add",
        parents=[shared],
        help="Add or replace a term in catalog/glossary.yml (or a sibling docs/glossary.yml)",
    )
    glossary_add.add_argument("term", help="Word or acronym to define")
    glossary_add.add_argument(
        "--meaning",
        help="One or two sentences. Required in chat; a local TTY can prompt",
    )
    glossary_add.add_argument(
        "--also",
        help="Comma-separated aliases (SOW, Statement of Work)",
    )
    glossary_add.add_argument(
        "--kind",
        choices=("acronym", "term"),
        help="Defaults to acronym when the term is ALL CAPS",
    )
    glossary_add.add_argument(
        "--see",
        help="Comma-separated related terms already in the glossary",
    )
    glossary_add.add_argument(
        "--repo",
        help="Write a product glossary in that sibling's docs/glossary.yml",
    )
    glossary_add.add_argument(
        "--replace",
        action="store_true",
        help="Update an existing term or alias in the same file",
    )
    glossary_add.add_argument("--dry-run", action="store_true")

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
            "(needs --workspace or GOAT_WORKSPACE)"
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

    skills = sub.add_parser(
        "skills",
        parents=[shared],
        help=(
            "List sibling agent skills and copy them into this Goat "
            ".github/skills folder so VS Code Agents can load them"
        ),
    )
    skills_sub = skills.add_subparsers(dest="skills_command", required=True)
    skills_list = skills_sub.add_parser(
        "list",
        parents=[shared],
        help="Discover skills in this goat and cloned sibling repos",
    )
    _add_scope_flags(skills_list)
    skills_list.add_argument("--repo", help="Comma-separated repository names")
    skills_list.add_argument(
        "--brief",
        action="store_true",
        help="Only name, description, source, and pick for each skill",
    )
    _add_skills_dest_flag(skills_list)
    skills_lift = skills_sub.add_parser(
        "lift",
        parents=[shared],
        help="Copy discovered skills into the root workspace .github/skills",
    )
    _add_scope_flags(skills_lift)
    skills_lift.add_argument("--repo", help="Comma-separated repository names")
    skills_lift.add_argument(
        "--only",
        help="Comma-separated skill names or source:name picks from skills list",
    )
    skills_lift.add_argument(
        "--all-skills",
        dest="all_skills",
        action="store_true",
        help="Lift every discovered skill without prompting (init/prepare already do this)",
    )
    skills_lift.add_argument(
        "--brief",
        action="store_true",
        help="Keep JSON to name + description (and lift results)",
    )
    _add_skills_dest_flag(skills_lift)
    skills_lift.add_argument(
        "--force",
        action="store_true",
        help="Replace an already-lifted copy from a different source",
    )
    skills_lift.add_argument("--dry-run", action="store_true")
    skills_pull = skills_sub.add_parser(
        "pull",
        parents=[shared],
        help="Clone a git repo of skills temporarily and install selected ones",
    )
    skills_pull.add_argument("url", help="Git URL of a skills repository")
    skills_pull.add_argument("--ref", help="Branch, tag, or commit to clone")
    skills_pull.add_argument(
        "--only",
        help="Comma-separated skill names to install from the cloned repo",
    )
    skills_pull.add_argument(
        "--all",
        dest="all_skills",
        action="store_true",
        help="Install every SKILL.md folder found in the cloned repo",
    )
    _add_skills_dest_flag(skills_pull)
    skills_pull.add_argument(
        "--force",
        action="store_true",
        help="Replace an already-lifted copy from a different source",
    )
    skills_pull.add_argument("--https", action="store_true", help="Rewrite git@github.com URLs to HTTPS")
    skills_pull.add_argument("--dry-run", action="store_true")

    sub.add_parser("catalog", parents=[shared], help="Show the resolved catalog")
    sub.add_parser("repos", parents=[shared], help="Show the repositories.yml manifest")
    return parser


def dispatch(args: argparse.Namespace) -> Any:
    if args.command in {"commands", "help"}:
        return command_reference(build_parser(), group=getattr(args, "group", None))
    if args.command in {"install", "uninstall"}:
        return _dispatch_install(args)
    goat_root = Path(args.root).resolve() if args.root else find_goat_root()
    load_dotenv_files(goat_root)
    catalog = load_catalog(
        goat_root,
        stack_path=Path(args.catalog).resolve() if args.catalog else None,
        repos_path=Path(args.repos).resolve() if args.repos else None,
        templates_path=Path(args.templates).resolve() if args.templates else None,
    )

    if args.command == "clone":
        only = _split_ids(args.only)
        tags = _split_ids(getattr(args, "tag", None))
        repos = clone_repos(
            catalog,
            goat_root,
            only=only,
            tags=tags,
            update=args.update,
            dry_run=args.dry_run,
            https=args.https,
        )
        payload = {
            "sibling_root": str(catalog.sibling_root(goat_root)),
            "repos": repos,
        }
        if any(item.get("action") == "blocked" for item in repos):
            raise _payload_error(
                "One or more repo URLs are still placeholders. Update repositories.yml.",
                payload,
            )
        return payload
    if args.command == "jira":
        return _dispatch_jira(args, catalog, goat_root)
    if args.command == "figma":
        return _dispatch_figma(args, catalog, goat_root)
    if args.command == "bruno":
        return _dispatch_bruno(args, catalog, goat_root)
    if args.command == "env":
        return _dispatch_env(args, catalog, goat_root)
    if args.command == "workspace":
        return _dispatch_workspace(args, catalog, goat_root)
    if args.command == "graph":
        return _dispatch_graph(args, catalog, goat_root)
    if args.command == "skills":
        return _dispatch_skills(args, catalog, goat_root)
    if args.command == "prepare":
        return prepare_issue(
            catalog,
            goat_root,
            _client(),
            args.issue,
            clone_missing=args.clone_missing,
            generate=not args.no_generate,
        )
    if args.command == "doctor":
        payload = run_doctor(
            catalog,
            goat_root,
            ping_jira=args.ping_jira,
            ping_figma=args.ping_figma,
            workspace_id=args.workspace,
            all_repos=bool(getattr(args, "all_repos", False)),
        )
        if not payload.get("ok"):
            raise _payload_error("Doctor found blocking issues.", payload)
        return payload
    if args.command == "init":
        return run_init(
            catalog,
            goat_root,
            interactive=args.interactive,
            ping_jira=args.ping_jira,
        )
    if args.command == "glossary":
        return _dispatch_glossary(args, catalog, goat_root)
    if args.command == "context":
        return collect_context(
            catalog,
            goat_root,
            only=_split_ids(args.repo),
            workspace_id=args.workspace,
            all_repos=bool(args.all_repos),
        )
    if args.command == "status":
        return collect_status(
            catalog,
            goat_root,
            only=_split_ids(args.repo),
            cwd=Path.cwd(),
            workspace_id=args.workspace,
            all_repos=bool(args.all_repos),
        )
    if args.command == "branch":
        return align_branches(
            catalog,
            goat_root,
            args.issue,
            only=_split_ids(args.repo),
            create=args.create,
            dry_run=args.dry_run,
            workspace_id=args.workspace,
            all_repos=bool(args.all_repos),
        )
    if args.command == "handoff":
        return _dispatch_handoff(args, catalog, goat_root)
    if args.command == "start":
        if args.action == "run":
            if args.shell:
                raise GoatError(
                    "goat start run starts the app. "
                    "Use `start env --repo <name> --shell` to apply env in a terminal."
                )
            repos = _split_ids(args.repo) or []
            if len(repos) != 1:
                raise GoatError("goat start run requires exactly one --repo")
            payload = execute_start_run(
                catalog,
                goat_root,
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
                raise GoatError("goat start env requires exactly one --repo")
            if args.save:
                raise GoatError("goat start env does not write a start plan")
            payload = execute_start_env(
                catalog,
                goat_root,
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
            goat_root,
            workspace_id=args.workspace,
            only=_split_ids(args.repo),
            save=args.save,
            refresh=args.refresh,
            all_repos=bool(getattr(args, "all_repos", False)),
        )
    if args.command == "catalog":
        return catalog_to_dict(catalog, goat_root)
    if args.command == "repos":
        payload = catalog_to_dict(catalog, goat_root)
        return {
            "manifest": payload["repos_source"],
            "parent_dir": payload["parent_dir"],
            "sibling_root": payload["sibling_root"],
            "repositories": payload["repos"],
        }
    if args.command == "templates":
        return _dispatch_templates(args, catalog)
    if args.command == "bootstrap":
        return _dispatch_bootstrap(args, catalog, goat_root)
    raise GoatError(f"Unknown command: {args.command}")


def _dispatch_jira(args: argparse.Namespace, catalog: Any, goat_root: Path) -> Any:
    settings = catalog.jira
    if args.jira_command == "schema":
        return {"jira": settings.schema()}
    if args.jira_command == "login":
        return login_token(
            goat_root,
            from_env=args.from_env,
            clear_env=not args.keep_env,
        )
    if args.jira_command == "logout":
        return logout_token(goat_root, clear_env=args.clear_env)
    client = _client()
    if args.jira_command == "get":
        return client.get_issue(args.issue, settings=settings)
    if args.jira_command == "comments":
        if not settings.wants("comments"):
            raise GoatError("Comments are disabled in catalog/stack.yaml jira.fields")
        return {
            "key": parse_issue_key(args.issue),
            "comments": client.get_comments(
                args.issue,
                max_results=settings.max_comments,
                settings=settings,
            ),
        }
    if args.jira_command == "search":
        return {
            "jql": args.jql,
            "issues": client.search(
                args.jql,
                max_results=args.max_results,
                settings=settings,
            ),
        }
    if args.jira_command == "context":
        return client.get_context(args.issue, settings=settings)
    if args.jira_command == "whoami":
        return client.myself()
    if args.jira_command == "mine":
        issues = client.search(
            JIRA_MINE_JQL, max_results=args.max_results, settings=settings
        )
        return {"jql": JIRA_MINE_JQL, "issues": issues}
    raise GoatError(f"Unknown jira command: {args.jira_command}")


def _dispatch_figma(args: argparse.Namespace, catalog: Any, goat_root: Path) -> Any:
    settings = catalog.figma
    variable = figma_var(catalog.env_vars)
    if args.figma_command == "schema":
        return {"figma": settings.schema()}
    if args.figma_command == "login":
        return set_env_value(
            variable,
            goat_root,
            from_env=args.from_env,
            clear_env=not args.keep_env,
        )
    if args.figma_command == "logout":
        return unset_env_value(variable, goat_root, clear_env=args.clear_env)
    client = _figma_client(catalog)
    if args.figma_command == "images":
        return client.get_images(
            args.file,
            ids=_split_ids(args.ids),
            image_format=args.image_format,
            scale=args.scale,
            settings=settings,
        )
    if args.figma_command == "comments":
        return client.get_comments(
            args.file,
            ids=_split_ids(args.ids),
            whole_file=bool(args.file_comments),
            settings=settings,
        )
    if args.figma_command == "nodes":
        return client.get_nodes(
            args.file,
            ids=_split_ids(args.ids),
            depth=args.depth,
            settings=settings,
        )
    if args.figma_command == "whoami":
        return client.myself()
    raise GoatError(f"Unknown figma command: {args.figma_command}")


def _dispatch_bruno(args: argparse.Namespace, catalog: Any, goat_root: Path) -> Any:
    settings = catalog.bruno
    if args.bruno_command == "schema":
        return {"bruno": settings.schema()}
    if args.bruno_command == "collections":
        return collect_bruno_inventory(catalog, goat_root, settings=settings)
    if args.bruno_command == "requests":
        return list_bruno_requests(
            catalog, goat_root, getattr(args, "target", None), settings=settings
        )
    if args.bruno_command == "envs":
        return list_bruno_envs(
            catalog, goat_root, getattr(args, "target", None), settings=settings
        )
    if args.bruno_command == "workflows":
        return list_bruno_workflows(
            catalog, goat_root, getattr(args, "name", None), settings=settings
        )
    if args.bruno_command == "run":
        return run_bruno_request(
            catalog,
            goat_root,
            args.target,
            collection=getattr(args, "collection", None),
            service=getattr(args, "service", None),
            env=getattr(args, "env", None),
            env_vars=getattr(args, "env_vars", None),
            dry_run=bool(getattr(args, "dry_run", False)),
            settings=settings,
        )
    raise GoatError(f"Unknown bruno command: {args.bruno_command}")


def _dispatch_env(args: argparse.Namespace, catalog: Any, goat_root: Path) -> Any:
    if args.env_command == "list":
        scope = resolve_workspace_scope(
            catalog,
            goat_root,
            workspace_id=args.workspace,
            all_repos=bool(getattr(args, "all_repos", False)),
        )
        extra = catalog.workspace(scope.id).env if scope.id else None
        payload = list_env(
            catalog.env_vars,
            goat_root,
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
            goat_root,
            from_env=args.from_env,
            clear_env=not args.keep_env,
        )
    if args.env_command == "unset":
        return unset_env_value(variable, goat_root, clear_env=args.clear_env)
    raise GoatError(f"Unknown env command: {args.env_command}")


def _dispatch_graph(args: argparse.Namespace, catalog: Any, goat_root: Path) -> Any:
    workspace_id = getattr(args, "workspace", None)
    if args.graph_command == "scan":
        return scan_workspace(
            catalog, goat_root, workspace_id=workspace_id, all_repos=not workspace_id
        )
    if args.graph_command == "build":
        payload = build_graph(
            catalog,
            goat_root,
            workspace_id=workspace_id,
            all_repos=not workspace_id,
            write=not args.no_write,
        )
        if not args.no_write:
            payload.pop("graph", None)
        return payload
    graph = load_graph(
        goat_root,
        Path(args.file).resolve()
        if getattr(args, "file", None)
        else (
            Path(args.graph_file).resolve()
            if getattr(args, "graph_file", None)
            else None
        ),
    )
    if args.graph_command == "validate":
        return {"kind": "workspace_graph_validate", **validate_graph(graph)}
    if args.graph_command == "explain":
        return explain_graph(graph, args.source, getattr(args, "target", None))
    if args.graph_command == "neighbors":
        return graph_neighbors(graph, args.node)
    if args.graph_command == "path":
        return path_between(graph, args.source, args.target)
    raise GoatError(f"Unknown graph command: {args.graph_command}")


def _dispatch_workspace(args: argparse.Namespace, catalog: Any, goat_root: Path) -> Any:
    if args.workspace_command == "list":
        return {"workspaces": list_workspaces(catalog, goat_root)}
    if args.workspace_command == "generate":
        if getattr(args, "check", False):
            status = check_workspaces(catalog, goat_root)
            if not status["ok"]:
                raise GoatError(workspace_sync_error(status), payload=status)
            return {"check": True, **status}
        workspaces = generate_workspaces(catalog, goat_root)
        return {
            "workspaces": workspaces,
            "skills": sync_root_skills(catalog, goat_root),
        }
    if args.workspace_command == "create":
        if getattr(args, "menu", False):
            return create_menu(catalog, goat_root)
        prompt = PromptSession(interactive=False if args.no_prompt else None)
        return create_workspace(
            catalog,
            goat_root,
            workspace_id=args.id,
            name=args.name,
            description=args.description,
            folders=_split_ids(args.projects),
            tags=_split_ids(args.tag),
            include_goat=args.include_goat,
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
        return open_workspace(catalog.workspace_file(goat_root, args.id))
    if args.workspace_command == "path":
        path = catalog.workspace_file(goat_root, args.id)
        return {"id": args.id, "file": str(path), "exists": path.exists()}
    if args.workspace_command == "current":
        return current_workspace_payload(
            catalog,
            goat_root,
            workspace_file=getattr(args, "workspace_file", None),
        )
    raise GoatError(f"Unknown workspace command: {args.workspace_command}")


def _dispatch_glossary(args: argparse.Namespace, catalog: Any, goat_root: Path) -> Any:
    if args.glossary_command == "add":
        if getattr(args, "all_repos", False) or getattr(args, "workspace", None):
            raise GoatError("goat glossary add writes one file; do not pass --workspace or --all")
        repos = _split_ids(getattr(args, "repo", None)) or []
        if len(repos) > 1:
            raise GoatError("goat glossary add accepts at most one --repo")
        return add_term(
            catalog,
            goat_root,
            args.term,
            meaning=args.meaning,
            also=_split_ids(args.also) or [],
            kind=args.kind,
            see=_split_ids(args.see) or [],
            repo=repos[0] if repos else None,
            replace=bool(args.replace),
            dry_run=bool(args.dry_run),
            prompt=PromptSession(),
        )
    return collect_glossary(
        catalog,
        goat_root,
        query=getattr(args, "term", None) or getattr(args, "query", None),
        action=args.glossary_command,
        kind=getattr(args, "kind", None),
        only=_split_ids(getattr(args, "repo", None)),
        workspace_id=getattr(args, "workspace", None),
        all_repos=bool(getattr(args, "all_repos", False)),
    )


def _dispatch_handoff(args: argparse.Namespace, catalog: Any, goat_root: Path) -> Any:
    if args.handoff_command == "list":
        return {"handoffs": list_handoffs(goat_root)}
    if args.handoff_command == "latest":
        return latest_handoff(goat_root)
    if args.handoff_command == "write":
        issue = parse_issue_key(args.issue) if args.issue else None
        status = collect_status(
            catalog,
            goat_root,
            workspace_id=getattr(args, "workspace", None),
            all_repos=bool(getattr(args, "all_repos", False)),
        )
        return write_handoff(
            goat_root,
            issue=issue,
            note=args.note,
            status=status,
        )
    raise GoatError(f"Unknown handoff command: {args.handoff_command}")


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


def _dispatch_bootstrap(args: argparse.Namespace, catalog: Any, goat_root: Path) -> Any:
    template_name = args.template_flag or args.template
    if args.template_flag and args.template and args.template_flag != args.template:
        raise GoatError("Positional template and --template do not match")
    if not template_name:
        raise GoatError(
            "Pass a listed template: goat bootstrap --template <name> --name <folder>"
        )
    return bootstrap_project(
        catalog,
        goat_root,
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


def _figma_client(catalog: Any) -> FigmaClient:
    return FigmaClient(figma_token_from_env(catalog.env_vars))


def _apply_leading_globals(args: argparse.Namespace, argv: list[str]) -> None:
    """Keep `goat --root X status` working.

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


def _dispatch_skills(args: argparse.Namespace, catalog: Any, goat_root: Path) -> Any:
    parent = bool(getattr(args, "parent", False))
    if args.skills_command == "list":
        return list_skills(
            catalog,
            goat_root,
            only=_split_ids(getattr(args, "repo", None)),
            workspace_id=getattr(args, "workspace", None),
            all_repos=bool(getattr(args, "all_repos", False)),
            parent=parent,
            brief=bool(getattr(args, "brief", False)),
        )
    if args.skills_command == "lift":
        return lift_skills(
            catalog,
            goat_root,
            only=_split_ids(getattr(args, "repo", None)),
            names=_split_ids(getattr(args, "only", None)),
            workspace_id=getattr(args, "workspace", None),
            all_repos=bool(getattr(args, "all_repos", False)),
            all_skills=bool(getattr(args, "all_skills", False)),
            parent=parent,
            force=bool(getattr(args, "force", False)),
            dry_run=bool(getattr(args, "dry_run", False)),
            brief=bool(getattr(args, "brief", False)),
            prompt=PromptSession(),
        )
    if args.skills_command == "pull":
        prompt = PromptSession()
        return pull_skills(
            catalog,
            goat_root,
            args.url,
            ref=getattr(args, "ref", None),
            names=_split_ids(getattr(args, "only", None)),
            all_skills=bool(getattr(args, "all_skills", False)),
            parent=parent,
            force=bool(getattr(args, "force", False)),
            dry_run=bool(getattr(args, "dry_run", False)),
            https=bool(getattr(args, "https", False)),
            prompt=prompt,
        )
    raise GoatError(f"Unknown skills command: {args.skills_command}")


def _dispatch_install(args: argparse.Namespace) -> Any:
    goat_root = resolve_install_root(getattr(args, "root", None))
    kwargs = {
        "bin_dir": getattr(args, "bin_dir", None),
        "force": bool(getattr(args, "force", False)),
        "dry_run": bool(getattr(args, "dry_run", False)),
    }
    if args.command == "uninstall":
        return uninstall_cli(goat_root, **kwargs)
    return install_cli(goat_root, **kwargs)


def _add_install_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--bin-dir",
        type=Path,
        help="Override the user bin directory (default: ~/.local/bin)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite or remove a file that is not a goat shim",
    )
    parser.add_argument("--dry-run", action="store_true")


def _add_skills_dest_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--parent",
        action="store_true",
        help=(
            "Copy into parent_dir/.github/skills instead of this Goat repo "
            "(for a single-folder window on the sibling root)"
        ),
    )


def _add_scope_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace",
        help="Feature workspace id (overrides GOAT_WORKSPACE)",
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


def _payload_error(message: str, payload: dict) -> GoatError:
    return GoatError(message, payload=payload)


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
