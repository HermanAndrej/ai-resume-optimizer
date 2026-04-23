from pathlib import Path

import pytest

from backend import paths


def test_windows_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\test\AppData\Roaming")

    assert paths.get_data_dir() == Path(r"C:\Users\test\AppData\Roaming\resume_optimizer")


def test_macos_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths.sys, "platform", "darwin")
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: Path("/Users/test")))

    assert paths.get_data_dir() == Path(
        "/Users/test/Library/Application Support/resume_optimizer"
    )


def test_linux_xdg_data_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/xdg")

    assert paths.get_data_dir() == Path("/tmp/xdg/resume_optimizer")


def test_linux_fallback_when_no_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: Path("/home/test")))

    assert paths.get_data_dir() == Path("/home/test/.local/share/resume_optimizer")
