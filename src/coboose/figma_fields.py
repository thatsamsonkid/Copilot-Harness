"""Config-driven allowlist for Copilot-facing Figma payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from coboose.projection import ProjectionSpec, project

DEFAULT_OUTPUT_FIELDS = [
    "file_key",
    "url",
    "format",
    "scale",
    "images",
    "missing",
]

DEFAULT_SHAPES: dict[str, tuple[str, ...]] = {
    "images": ("id", "url"),
}

DEFAULT_FORMAT = "png"
DEFAULT_SCALE = 2.0
DEFAULT_MAX_IDS = 12
ALLOWED_FORMATS = ("png", "jpg", "svg", "pdf")


def _copy_shapes(source: dict[str, tuple[str, ...] | list[str]] | None = None) -> dict[str, list[str]]:
    items = source if source is not None else DEFAULT_SHAPES
    return {key: list(value) for key, value in items.items()}


@dataclass(frozen=True)
class FigmaSettings:
    fields: list[str] = field(default_factory=lambda: list(DEFAULT_OUTPUT_FIELDS))
    shapes: dict[str, list[str]] = field(default_factory=_copy_shapes)
    default_format: str = DEFAULT_FORMAT
    default_scale: float = DEFAULT_SCALE
    max_ids: int = DEFAULT_MAX_IDS
    drop_empty: bool = True

    def output_fields(self) -> list[str]:
        names = list(self.fields or DEFAULT_OUTPUT_FIELDS)
        if "file_key" not in names:
            names.insert(0, "file_key")
        if "images" not in names:
            names.append("images")
        return names

    def wants(self, name: str) -> bool:
        return name in set(self.output_fields())

    def images_projection(self) -> ProjectionSpec:
        return ProjectionSpec(
            name="figma.images",
            fields=tuple(self.output_fields()),
            shapes={key: tuple(value) for key, value in self.shapes.items()},
            drop_empty=self.drop_empty,
        )

    def image_item_projection(self) -> ProjectionSpec:
        return self.images_projection().nested("images", DEFAULT_SHAPES["images"])

    def schema(self) -> dict[str, Any]:
        return {
            "fields": self.output_fields(),
            "shapes": {key: list(value) for key, value in self.shapes.items()},
            "default_format": self.default_format,
            "default_scale": self.default_scale,
            "max_ids": self.max_ids,
            "drop_empty": self.drop_empty,
        }


def project_images(payload: dict[str, Any], settings: FigmaSettings) -> dict[str, Any]:
    """Keep only configured output fields. Never pass through a raw Figma payload."""
    projected = project(payload, settings.images_projection())
    if settings.wants("images") and "images" not in projected:
        projected["images"] = []
    return projected
