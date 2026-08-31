"""Config-driven allowlist for Copilot-facing Figma payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from goat.projection import ProjectionSpec, project

DEFAULT_OUTPUT_FIELDS = [
    "file_key",
    "url",
    "format",
    "scale",
    "images",
    "missing",
]

DEFAULT_COMMENT_FIELDS = [
    "file_key",
    "url",
    "comments",
]

DEFAULT_SHAPES: dict[str, tuple[str, ...]] = {
    "images": ("id", "url"),
    "comments": ("author", "created", "message", "node_id", "resolved"),
}

DEFAULT_FORMAT = "png"
DEFAULT_SCALE = 2.0
DEFAULT_MAX_IDS = 12
DEFAULT_MAX_COMMENTS = 30
DEFAULT_DEPTH = 2
DEFAULT_MAX_DEPTH = 3
ALLOWED_FORMATS = ("png", "jpg", "svg", "pdf")
NODES_NOTE = (
    "Raw Figma node JSON. Use only on a small targeted frame so the tree "
    "does not overwhelm Copilot context."
)


def _copy_shapes(source: dict[str, tuple[str, ...] | list[str]] | None = None) -> dict[str, list[str]]:
    items = source if source is not None else DEFAULT_SHAPES
    return {key: list(value) for key, value in items.items()}


@dataclass(frozen=True)
class FigmaSettings:
    fields: list[str] = field(default_factory=lambda: list(DEFAULT_OUTPUT_FIELDS))
    comment_fields: list[str] = field(default_factory=lambda: list(DEFAULT_COMMENT_FIELDS))
    shapes: dict[str, list[str]] = field(default_factory=_copy_shapes)
    default_format: str = DEFAULT_FORMAT
    default_scale: float = DEFAULT_SCALE
    max_ids: int = DEFAULT_MAX_IDS
    include_comments: bool = True
    max_comments: int = DEFAULT_MAX_COMMENTS
    default_depth: int = DEFAULT_DEPTH
    max_depth: int = DEFAULT_MAX_DEPTH
    drop_empty: bool = True

    def output_fields(self) -> list[str]:
        names = list(self.fields or DEFAULT_OUTPUT_FIELDS)
        if "file_key" not in names:
            names.insert(0, "file_key")
        if "images" not in names:
            names.append("images")
        return names

    def comment_output_fields(self) -> list[str]:
        names = list(self.comment_fields or DEFAULT_COMMENT_FIELDS)
        if "file_key" not in names:
            names.insert(0, "file_key")
        if self.include_comments and "comments" not in names:
            names.append("comments")
        if not self.include_comments:
            names = [name for name in names if name != "comments"]
        return names

    def wants(self, name: str) -> bool:
        return name in set(self.output_fields())

    def wants_comments(self) -> bool:
        return self.include_comments and "comments" in set(self.comment_output_fields())

    def images_projection(self) -> ProjectionSpec:
        return ProjectionSpec(
            name="figma.images",
            fields=tuple(self.output_fields()),
            shapes={key: tuple(value) for key, value in self.shapes.items()},
            drop_empty=self.drop_empty,
        )

    def comments_projection(self) -> ProjectionSpec:
        return ProjectionSpec(
            name="figma.comments",
            fields=tuple(self.comment_output_fields()),
            shapes={key: tuple(value) for key, value in self.shapes.items()},
            drop_empty=self.drop_empty,
        )

    def comment_item_projection(self) -> ProjectionSpec:
        return self.comments_projection().nested("comments", DEFAULT_SHAPES["comments"])

    def image_item_projection(self) -> ProjectionSpec:
        return self.images_projection().nested("images", DEFAULT_SHAPES["images"])

    def schema(self) -> dict[str, Any]:
        return {
            "fields": self.output_fields(),
            "comment_fields": self.comment_output_fields(),
            "shapes": {key: list(value) for key, value in self.shapes.items()},
            "default_format": self.default_format,
            "default_scale": self.default_scale,
            "max_ids": self.max_ids,
            "include_comments": self.wants_comments(),
            "max_comments": self.max_comments,
            "default_depth": self.default_depth,
            "max_depth": self.max_depth,
            "raw_nodes": True,
            "nodes_note": NODES_NOTE,
            "drop_empty": self.drop_empty,
        }


def project_images(payload: dict[str, Any], settings: FigmaSettings) -> dict[str, Any]:
    """Keep only configured output fields. Never pass through a raw Figma payload."""
    projected = project(payload, settings.images_projection())
    if settings.wants("images") and "images" not in projected:
        projected["images"] = []
    return projected


def project_comments(payload: dict[str, Any], settings: FigmaSettings) -> dict[str, Any]:
    projected = project(payload, settings.comments_projection())
    if settings.wants_comments() and "comments" not in projected:
        projected["comments"] = []
    return projected
