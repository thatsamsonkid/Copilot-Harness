from __future__ import annotations

import argparse
from typing import Any

from coboose import CobooseError

SHARED_DESTS = frozenset({"format", "catalog", "repos", "templates", "root"})

EXPANDED_HELPS = {
    "start": "Print a workspace start plan (does not launch)",
    "start run": "Start one repo with launch.json env loaded in-process",
    "start env": "List or apply one repo's launch env (keys only on stdout)",
}

GROUP_ORDER = (
    "commands",
    "init",
    "doctor",
    "env",
    "clone",
    "repos",
    "catalog",
    "templates",
    "bootstrap",
    "workspace",
    "prepare",
    "jira",
    "figma",
    "bruno",
    "context",
    "status",
    "branch",
    "handoff",
    "start",
    "skills",
)


def command_reference(
    parser: argparse.ArgumentParser,
    group: str | None = None,
) -> dict[str, Any]:
    commands = collect_commands(parser)
    groups = _ordered_groups({item["group"] for item in commands})
    if group:
        needle = group.strip().lower()
        commands = [
            item
            for item in commands
            if item["group"] == needle
            or item["command"] == needle
            or item["command"].startswith(f"{needle} ")
        ]
        if not commands:
            raise CobooseError(
                f"Unknown command group {group!r}. Try: {', '.join(groups)}"
            )
        groups = _ordered_groups({item["group"] for item in commands})
    commands = _sort_commands(commands)
    return {
        "kind": "command_reference",
        "count": len(commands),
        "groups": groups,
        "shared": _shared_flags(parser),
        "commands": commands,
    }


def collect_commands(parser: argparse.ArgumentParser) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in _walk(parser, prefix="", help_text=""):
        items.extend(_expand_optional_choices(item))
    return items


def _walk(
    parser: argparse.ArgumentParser, prefix: str, help_text: str
) -> list[dict[str, Any]]:
    action = _subparsers_action(parser)
    if action is None:
        if not prefix:
            return []
        return [_describe_command(parser, prefix, help_text)]
    items: list[dict[str, Any]] = []
    seen: set[int] = set()
    helps = _choice_helps(action)
    for name, sub in action.choices.items():
        if id(sub) in seen:
            continue
        seen.add(id(sub))
        path = f"{prefix} {name}".strip()
        items.extend(_walk(sub, path, helps.get(name, "")))
    return items


def _describe_command(
    parser: argparse.ArgumentParser, path: str, help_text: str
) -> dict[str, Any]:
    arguments = [
        described
        for action in parser._actions
        if (described := _describe_argument(action)) is not None
    ]
    return {
        "command": path,
        "group": path.split()[0],
        "help": _first_sentence(help_text or parser.description or ""),
        "usage": _usage(path, arguments),
        "arguments": arguments,
    }


def _describe_argument(action: argparse.Action) -> dict[str, Any] | None:
    if isinstance(
        action,
        (
            argparse._HelpAction,
            argparse._VersionAction,
            argparse._SubParsersAction,
        ),
    ):
        return None
    if action.dest in SHARED_DESTS:
        return None
    option_strings = list(action.option_strings)
    kind = "option" if option_strings else "positional"
    name = option_strings[0] if option_strings else str(action.dest)
    payload: dict[str, Any] = {
        "name": name,
        "kind": kind,
        "required": (
            bool(action.required) if option_strings else _positional_required(action)
        ),
    }
    help_text = (action.help or "").strip()
    if help_text:
        payload["help"] = help_text
    aliases = option_strings[1:]
    if aliases:
        payload["aliases"] = aliases
    if action.choices:
        payload["choices"] = [str(choice) for choice in action.choices]
    return payload


def _expand_optional_choices(item: dict[str, Any]) -> list[dict[str, Any]]:
    arguments = item["arguments"]
    choice_args = [
        arg
        for arg in arguments
        if arg["kind"] == "positional" and arg.get("choices") and not arg["required"]
    ]
    if len(choice_args) != 1:
        return [item]
    choice_arg = choice_args[0]
    rest = [arg for arg in arguments if arg is not choice_arg]
    base_command = item["command"]
    base = {
        **item,
        "help": EXPANDED_HELPS.get(base_command, item["help"]),
        "arguments": rest,
        "usage": _usage(base_command, rest),
    }
    extras = []
    for choice in choice_arg["choices"]:
        command = f"{base_command} {choice}"
        extras.append(
            {
                **item,
                "command": command,
                "help": EXPANDED_HELPS.get(command, item["help"]),
                "arguments": rest,
                "usage": _usage(command, rest),
            }
        )
    return [base, *extras]


def _usage(command: str, arguments: list[dict[str, Any]]) -> str:
    parts = ["coboose", *command.split()]
    for arg in arguments:
        if arg["kind"] != "positional":
            continue
        if arg.get("choices"):
            token = "|".join(arg["choices"])
        else:
            token = str(arg["name"]).upper()
        if not arg["required"]:
            token = f"[{token}]"
        parts.append(token)
    return " ".join(parts)


def _shared_flags(parser: argparse.ArgumentParser) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for action in parser._actions:
        if action.dest not in SHARED_DESTS or not action.option_strings:
            continue
        item: dict[str, Any] = {
            "name": action.option_strings[0],
            "help": (action.help or "").strip(),
        }
        if action.choices:
            item["choices"] = [str(choice) for choice in action.choices]
        flags.append(item)
    return flags


def _subparsers_action(
    parser: argparse.ArgumentParser,
) -> argparse._SubParsersAction | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _choice_helps(action: argparse._SubParsersAction) -> dict[str, str]:
    helps: dict[str, str] = {}
    for choice in getattr(action, "_choices_actions", []):
        helps[choice.dest] = choice.help or ""
    return helps


def _positional_required(action: argparse.Action) -> bool:
    return action.nargs not in (
        argparse.OPTIONAL,
        argparse.ZERO_OR_MORE,
        argparse.REMAINDER,
        "?",
        "*",
    )


def _first_sentence(text: str) -> str:
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""
    index = cleaned.find(". ")
    if index != -1:
        return cleaned[:index]
    return cleaned.rstrip(".")


def _sort_commands(commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    index = {name: i for i, name in enumerate(GROUP_ORDER)}
    return sorted(
        commands,
        key=lambda item: (
            index.get(item["group"], len(GROUP_ORDER)),
            item["command"],
        ),
    )


def _ordered_groups(found: set[str]) -> list[str]:
    ordered = [name for name in GROUP_ORDER if name in found]
    extra = sorted(found - set(GROUP_ORDER))
    return ordered + extra
