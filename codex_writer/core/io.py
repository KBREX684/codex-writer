import json
import os
import tempfile
from pathlib import Path

from codex_writer.core.errors import AtomicWriteError


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp", prefix=path.stem)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise
        os.replace(tmp_path, str(path))
    except OSError as e:
        raise AtomicWriteError(f"原子写入失败: {path} -> {e}")


def read_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_markdown_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp", prefix=path.stem)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise
        os.replace(tmp_path, str(path))
    except OSError as e:
        raise AtomicWriteError(f"原子写入失败: {path} -> {e}")


_JSON_STORE_CACHE: dict = {}

def read_json_store(path: Path, default: dict) -> dict:
    if path.exists():
        return read_json(path)
    return default

def write_json_store(path: Path, data: dict) -> None:
    write_json_atomic(path, data)


def append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        f.flush()
