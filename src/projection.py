"""Config-driven allowlist for Copilot-facing API payloads.

Integrations normalize a vendor response into a plain dict, then call
`project()`. The allowlist lives in catalog YAML so adding or removing a
field is a config change, not a client rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from goat import GoatError

_EMPTY = (None, "", [], {})


@dataclass(frozen=True)
class ProjectionSpec:
    """Allowlist plus optional nested shapes.

    `fields` is the top-level key order Copilot is allowed to see.
    `shapes` further clips dict (or list-of-dict) values for a named field.
    """

    fields: tuple[str, ...]
    shapes: dict[str, tuple[str, ...]] = field(default_factory=dict)
    drop_empty: bool = True
    name: str = ""

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any] | None,
        *,
        name: str = "",
        default_fields: list[str] | tuple[str, ...] | None = None,
        default_shapes: Mapping[str, tuple[str, ...] | list[str]] | None = None,
        default_drop_empty: bool = True,
    ) -> ProjectionSpec:
        data = dict(raw or {})
        label = f"{name} " if name else ""
        if "fields" in data:
            fields = _as_str_list(data.get("fields"), label=f"{label}fields")
        else:
            fields = [str(item) for item in default_fields or ()]
        shapes = {
            str(key): tuple(str(item) for item in value)
            for key, value in (default_shapes or {}).items()
        }
        shapes_raw = data.get("shapes")
        if shapes_raw is None:
            shapes_raw = {}
        if not isinstance(shapes_raw, Mapping):
            raise GoatError(f"{label}shapes must be a mapping of field to nested keys")
        for key, value in shapes_raw.items():
            shapes[str(key)] = tuple(_as_str_list(value, label=f"{label}shape {key}"))
        drop_empty = data.get("drop_empty")
        return cls(
            fields=tuple(fields),
            shapes=shapes,
            drop_empty=default_drop_empty if drop_empty is None else bool(drop_empty),
            name=name,
        )

    def nested(self, field_name: str, fallback: tuple[str, ...] | list[str]) -> ProjectionSpec:
        """Projection for a list of nested objects (comments, labels, …)."""
        nested_fields = self.shapes.get(field_name) or tuple(fallback)
        return ProjectionSpec(
            fields=tuple(nested_fields),
            drop_empty=self.drop_empty,
            name=f"{self.name}.{field_name}" if self.name else field_name,
        )


def project(
    payload: Any,
    spec: ProjectionSpec,
    *,
    shape: tuple[str, ...] | None = None,
) -> Any:
    """Keep only configured keys. Never pass a raw vendor payload through."""
    allowed = list(spec.fields if shape is None else shape)
    if isinstance(payload, list):
        projected = [
            project(item, spec, shape=tuple(allowed))
            if isinstance(item, (dict, list))
            else item
            for item in payload
        ]
        if spec.drop_empty:
            projected = [item for item in projected if not _is_empty(item)]
        return projected
    if not isinstance(payload, dict):
        return payload

    out: dict[str, Any] = {}
    for name in allowed:
        if name not in payload:
            continue
        value = payload[name]
        nested = spec.shapes.get(name)
        if nested is not None and isinstance(value, (dict, list)):
            value = project(value, spec, shape=nested)
        if spec.drop_empty and _is_empty(value):
            continue
        out[name] = value
    return out


def _is_empty(value: Any) -> bool:
    return value in _EMPTY


def _as_str_list(value: Any, *, label: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    raise GoatError(f"Expected {label} to be a list or string, got {type(value).__name__}")
