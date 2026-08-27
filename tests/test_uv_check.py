from __future__ import annotations

from harness.uv_check import detect_uv, os_family, uv_missing_action


def test_os_family():
    assert os_family("Darwin") == "macos"
    assert os_family("Windows") == "windows"
    assert os_family("Linux") == "linux"


def test_missing_uv_points_at_windows_install():
    info = detect_uv(which=lambda _name: None, system="Windows")
    assert info["present"] is False
    assert info["os"] == "windows"
    assert info["setup_script"] == ".\\scripts\\setup.ps1"
    assert "install.ps1" in info["install_command"]
    assert "docs/install-uv.md" in uv_missing_action(info)
    assert "Windows" in uv_missing_action(info)


def test_missing_uv_points_at_macos_install():
    info = detect_uv(which=lambda _name: None, system="Darwin")
    assert info["setup_script"] == "./scripts/setup.sh"
    assert "install.sh" in info["install_command"]
    assert "macOS" in uv_missing_action(info)


def test_present_uv_includes_all_os_commands():
    info = detect_uv(which=lambda _name: "/usr/bin/uv", system="Linux")
    assert info["present"] is True
    assert info["install"]["windows"]["setup_script"] == ".\\scripts\\setup.ps1"
    assert info["install"]["macos"]["command"].startswith("curl")
