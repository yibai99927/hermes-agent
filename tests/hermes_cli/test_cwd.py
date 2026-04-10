from pathlib import Path
from unittest.mock import patch

from hermes_cli.cwd import resolve_runtime_cwd


def test_resolve_runtime_cwd_prefers_terminal_env(monkeypatch):
    monkeypatch.setenv("TERMINAL_CWD", "/tmp/project")
    monkeypatch.setattr("hermes_cli.cwd.os.getcwd", lambda: "/root")
    assert resolve_runtime_cwd(".") == "/tmp/project"


def test_resolve_runtime_cwd_expands_relative_paths_from_terminal_env(monkeypatch):
    monkeypatch.setenv("TERMINAL_CWD", "/tmp/project")
    assert resolve_runtime_cwd("src") == "/tmp/project/src"


def test_resolve_runtime_cwd_falls_back_to_home_when_process_cwd_is_unusable(monkeypatch, tmp_path):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.delenv("TERMINAL_CWD", raising=False)
    monkeypatch.setattr("hermes_cli.cwd.os.getcwd", lambda: str(tmp_path / "missing-cwd"))
    with patch.object(Path, "home", return_value=fake_home):
        assert resolve_runtime_cwd() == str(fake_home)
