from __future__ import annotations

from pathlib import Path

from harness.doctor import run_doctor


def test_doctor_advises_missing_verify_on_cloned_repo(harness_root: Path, catalog):
    repo = harness_root.parent / "frontend"
    repo.mkdir()
    (repo / "README.md").write_text("# frontend\n", encoding="utf-8")
    payload = run_doctor(catalog, harness_root)
    assert payload["ok"] is True
    checks = {check["name"]: check for check in payload["checks"]}
    assert checks["instructions:frontend"]["ok"] is False
    assert checks["instructions:frontend"]["advisory"] is True
    assert checks["verify:frontend"]["ok"] is False
    assert checks["verify:frontend"]["advisory"] is True
    frontend = next(item for item in payload["repos"] if item["id"] == "frontend")
    assert frontend["readiness"]["ok"] is False
    assert frontend["suggested_verify"] == []


def test_doctor_passes_verify_when_makefile_exists(harness_root: Path, catalog):
    repo = harness_root.parent / "frontend"
    repo.mkdir()
    (repo / "AGENTS.md").write_text("Run make check.\n", encoding="utf-8")
    (repo / "Makefile").write_text("check:\n\ttrue\n", encoding="utf-8")
    payload = run_doctor(catalog, harness_root)
    checks = {check["name"]: check for check in payload["checks"]}
    assert checks["instructions:frontend"]["ok"] is True
    assert checks["verify:frontend"]["ok"] is True
    assert checks["verify:frontend"]["detail"] == "make check"
