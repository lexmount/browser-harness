import os

import pytest

from browser_harness import auth


def test_write_private_json_writes_content(tmp_path):
    path = tmp_path / "creds.json"

    auth._write_private_json(path, {"k": "v"})

    assert path.read_text() == '{\n  "k": "v"\n}\n'


def test_write_private_json_does_not_double_close_fd_when_write_fails(tmp_path, monkeypatch):
    """Once os.fdopen succeeds the file object owns the fd; a manual os.close
    after the file object closed it could close a descriptor another thread
    has since been handed."""
    path = tmp_path / "creds.json"
    real_fdopen = os.fdopen
    manual_closes = []

    class ExplodingFile:
        def __init__(self, f):
            self._f = f

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self._f.close()  # the fd is now closed, as with a real file object
            return False

        def write(self, data):
            raise OSError("disk full")

    monkeypatch.setattr(os, "fdopen", lambda fd, *a, **k: ExplodingFile(real_fdopen(fd, *a, **k)))
    monkeypatch.setattr(os, "close", lambda fd: manual_closes.append(fd))

    with pytest.raises(OSError, match="disk full"):
        auth._write_private_json(path, {"k": "v"})

    assert manual_closes == [], "fd must not be closed again after the file object closed it"


def test_write_private_json_closes_fd_when_fdopen_fails(tmp_path, monkeypatch):
    path = tmp_path / "creds.json"
    real_close = os.close
    closed = []

    def failing_fdopen(*args, **kwargs):
        raise MemoryError("boom")

    def tracking_close(fd):
        closed.append(fd)
        real_close(fd)

    monkeypatch.setattr(os, "fdopen", failing_fdopen)
    monkeypatch.setattr(os, "close", tracking_close)

    with pytest.raises(MemoryError):
        auth._write_private_json(path, {"k": "v"})

    assert len(closed) == 1, "the raw fd must be closed when os.fdopen fails"
