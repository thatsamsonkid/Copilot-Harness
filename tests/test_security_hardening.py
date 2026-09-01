from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from goat import GoatError
from goat.clone import clone_one, validate_git_ref, validate_git_url
from goat.catalog import Repo
from goat.http import HttpClient
from goat.jira_client import jira_settings_from_env
from goat.paths import load_dotenv_files
from goat.skills import pull_skills


# --- git URL / ref validation -------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/acme/web.git",
        "ssh://git@github.com/acme/web.git",
        "git@github.com:acme/web.git",
        "/local/mirror/web.git",
        "../sibling/web.git",
    ],
)
def test_validate_git_url_accepts_safe_forms(url):
    assert validate_git_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "ext::sh -c 'touch /tmp/pwned'",
        "fd::17/foo",
        "--upload-pack=touch /tmp/pwned",
        "-oProxyCommand=evil",
        "file:///etc/passwd",
        "http://insecure.example/repo.git",
        "git://insecure.example/repo.git",
        "",
    ],
)
def test_validate_git_url_rejects_dangerous_forms(url):
    with pytest.raises(GoatError):
        validate_git_url(url)


def test_validate_git_ref_rejects_option_like_and_control():
    assert validate_git_ref("main") == "main"
    with pytest.raises(GoatError):
        validate_git_ref("--upload-pack=evil")
    with pytest.raises(GoatError):
        validate_git_ref("bad ref")


def test_clone_command_is_hardened(tmp_path):
    calls: list[list[str]] = []

    def run(command, cwd):
        calls.append(command)

    repo = Repo(
        name="web",
        url="https://github.com/acme/web.git",
        path="web",
        default_branch="main",
    )
    dest = tmp_path / "siblings" / "web"
    clone_one(repo, dest, sibling_root=tmp_path / "siblings", run=run)
    command = calls[0]
    assert "-c" in command and "protocol.ext.allow=never" in command
    # positional url/dest are separated from options by `--`
    assert "--" in command
    assert command.index("--") < command.index("https://github.com/acme/web.git")


def test_clone_one_rejects_ext_transport_url(tmp_path):
    repo = Repo(
        name="evil",
        url="ext::sh -c touch",
        path="evil",
        default_branch="main",
    )
    dest = tmp_path / "siblings" / "evil"
    with pytest.raises(GoatError):
        clone_one(repo, dest, sibling_root=tmp_path / "siblings", run=lambda c, d: None)


def test_pull_skills_rejects_ext_transport(catalog, goat_root: Path):
    with pytest.raises(GoatError):
        pull_skills(catalog, goat_root, "ext::sh -c touch", run=lambda c, d: None)


# --- HTTP redirects are not followed -----------------------------------------


class _RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - stdlib naming
        if self.path == "/start":
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:%d/target" % self.server.server_port)
            self.end_headers()
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{\"reached\": true}")

    def log_message(self, *args):  # silence test server logging
        return


def test_http_client_does_not_follow_redirects():
    server = HTTPServer(("127.0.0.1", 0), _RedirectHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/start"
        response = HttpClient().request("GET", url, headers={"Authorization": "Basic secret"})
        # The 302 is surfaced, not silently followed to /target.
        assert response.status == 302
        assert "reached" not in (response.body or "")
    finally:
        server.shutdown()
        thread.join()


# --- Jira base URL must be HTTPS ---------------------------------------------


def _set_jira_env(monkeypatch, base_url: str):
    monkeypatch.setenv("JIRA_BASE_URL", base_url)
    monkeypatch.setenv("JIRA_EMAIL", "ada@acme.test")
    monkeypatch.setenv("JIRA_API_TOKEN", "token-value")


def test_jira_settings_requires_https(monkeypatch, isolated_keychain):
    _set_jira_env(monkeypatch, "http://acme.atlassian.net")
    with pytest.raises(GoatError, match="https"):
        jira_settings_from_env()


def test_jira_settings_allows_https_and_localhost_http(monkeypatch, isolated_keychain):
    _set_jira_env(monkeypatch, "https://acme.atlassian.net")
    base_url, email, token = jira_settings_from_env()
    assert base_url == "https://acme.atlassian.net"

    _set_jira_env(monkeypatch, "http://localhost:8080")
    base_url, _email, _token = jira_settings_from_env()
    assert base_url == "http://localhost:8080"


# --- cwd .env is not loaded ---------------------------------------------------


def test_load_dotenv_ignores_cwd_env(tmp_path, monkeypatch):
    monkeypatch.delenv("GOAT_SECURITY_PROBE", raising=False)
    root = tmp_path / "goat"
    root.mkdir()
    (root / ".env").write_text("GOAT_SECURITY_PROBE=from_root\n", encoding="utf-8")

    hostile_cwd = tmp_path / "sibling"
    hostile_cwd.mkdir()
    (hostile_cwd / ".env").write_text("GOAT_SECURITY_PROBE=from_cwd\n", encoding="utf-8")
    monkeypatch.chdir(hostile_cwd)

    load_dotenv_files(root)
    import os

    assert os.environ.get("GOAT_SECURITY_PROBE") == "from_root"
    monkeypatch.delenv("GOAT_SECURITY_PROBE", raising=False)
