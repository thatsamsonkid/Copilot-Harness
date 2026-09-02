from __future__ import annotations

from pathlib import Path

import yaml

from goat.catalog import Repo
from goat.languages import discover_languages, normalize_language

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".github" / "skills"
INSTRUCTIONS = ROOT / ".github" / "instructions"
PROMPTS = ROOT / ".github" / "prompts"

PACKS = ("typescript", "python", "java")


def _frontmatter_and_body(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, raw_meta, body = text.split("---", 2)
    meta = yaml.safe_load(raw_meta)
    assert isinstance(meta, dict)
    return meta, body


def _repo(**kwargs) -> Repo:
    values = {
        "name": "demo",
        "url": "https://github.com/acme/demo.git",
        "path": "demo",
        "tags": ["api"],
    }
    values.update(kwargs)
    return Repo(**values)


def test_each_language_skill_matches_directory_and_points_at_context():
    for name in PACKS:
        skill = SKILLS / name / "SKILL.md"
        meta, body = _frontmatter_and_body(skill)
        assert meta["name"] == name
        description = meta["description"].lower()
        assert name in description
        lowered = body.lower()
        for token in (
            "uv run goat context",
            "suggested_verify",
            "cannot spawn",
            "--project",
            "do not copy",
            f".github/instructions/{name}.instructions.md",
        ):
            assert token in lowered, f"{name} skill missing {token!r}"


def test_language_skills_cover_toolchain_and_hard_rules():
    _, ts = _frontmatter_and_body(SKILLS / "typescript" / "SKILL.md")
    for token in ("pnpm", "any", "generated", "lockfile"):
        assert token in ts.lower()

    _, py = _frontmatter_and_body(SKILLS / "python" / "SKILL.md")
    for token in ("uv run pytest", "pip install", "this goat", "sibling"):
        assert token in py.lower()

    _, java = _frontmatter_and_body(SKILLS / "java" / "SKILL.md")
    for token in ("launch.json", "goat start run", "mvnw", "gradlew"):
        assert token in java.lower()


def test_path_instructions_apply_to_language_globs():
    expected = {
        "typescript": "**/*.ts,**/*.tsx,**/*.mts,**/*.cts",
        "python": "**/*.py,**/*.pyi",
        "java": "**/*.java",
    }
    for name, apply_to in expected.items():
        path = INSTRUCTIONS / f"{name}.instructions.md"
        meta, body = _frontmatter_and_body(path)
        assert meta["applyTo"] == apply_to
        assert f".github/skills/{name}/SKILL.md" in body


def test_prompts_load_matching_skill():
    for name in PACKS:
        path = PROMPTS / f"{name}.prompt.md"
        meta, body = _frontmatter_and_body(path)
        assert meta["name"] == name
        lowered = body.lower()
        assert f"{name}/skill.md" in lowered
        assert "goat context" in lowered


def test_normalize_language_aliases():
    assert normalize_language("ts") == "typescript"
    assert normalize_language("Django") == "python"
    assert normalize_language("spring-boot") == "java"
    assert normalize_language("fortran") is None


def test_discover_languages_prefers_declared_then_files(tmp_path: Path):
    repo = _repo(language="python", tags=["spring"])
    (tmp_path / "pom.xml").write_text("<project/>\n", encoding="utf-8")
    payload = discover_languages(repo, tmp_path, cloned=True, markers=["pom"])
    assert payload["language"] == "python"
    assert [item["id"] for item in payload["languages"]] == ["python", "java"]
    assert payload["skill"] == ".github/skills/python/SKILL.md"
    assert payload["languages"][0]["source"] == "declared"
    assert payload["languages"][1]["source"] == "tags"


def test_discover_languages_from_tsconfig(tmp_path: Path):
    repo = _repo(tags=["ui"])
    (tmp_path / "tsconfig.json").write_text("{}\n", encoding="utf-8")
    payload = discover_languages(repo, tmp_path, cloned=True)
    assert payload["language"] == "typescript"
    assert payload["languages"][0]["source"] == "files"


def test_discover_languages_uncloned_uses_tags_only(tmp_path: Path):
    repo = _repo(tags=["angular"])
    payload = discover_languages(repo, tmp_path, cloned=False)
    assert payload["language"] == "typescript"
    assert payload["languages"][0]["source"] == "tags"
