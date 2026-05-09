import threading

import pytest

from codex_writer.core.io import AtomicWriteError, write_json_atomic
from codex_writer.core.locks import LockAlreadyHeld, project_write_lock


def test_atomic_write_failure_preserves_original(monkeypatch, tmp_path):
    target = tmp_path / "state.json"
    target.write_text('{"chapter": 1}', encoding="utf-8")

    def boom(*args, **kwargs):
        raise OSError("simulated fs failure")

    monkeypatch.setattr("os.replace", boom)
    with pytest.raises(AtomicWriteError):
        write_json_atomic(target, {"chapter": 2})
    assert target.read_text(encoding="utf-8") == '{"chapter": 1}'


def test_concurrent_write_lock_allows_only_one_writer(tmp_path):
    acquired = []
    errors = []

    def worker():
        try:
            with project_write_lock(tmp_path, timeout=0.1):
                acquired.append(True)
        except LockAlreadyHeld:
            errors.append(True)

    with project_write_lock(tmp_path, timeout=0.1):
        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()

    assert acquired == []
    assert errors == [True]
