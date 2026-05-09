from pathlib import Path

from filelock import FileLock, Timeout as FileLockTimeout

from codex_writer.core.errors import LockAlreadyHeld
from codex_writer.core.paths import lock_path

DEFAULT_LOCK_TIMEOUT = 30


class project_write_lock:
    def __init__(self, project_root: Path, timeout: float = DEFAULT_LOCK_TIMEOUT):
        self._path = lock_path(project_root)
        self._timeout = timeout
        self._lock = FileLock(str(self._path), timeout=timeout)

    def __enter__(self):
        try:
            self._lock.acquire(timeout=self._timeout)
        except FileLockTimeout:
            raise LockAlreadyHeld("项目写锁被占用，请稍后重试")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._lock.release()
        return False
