import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def validate_csv(path: Path) -> list[str]:
    errors = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"无法读取文件: {e}"]

    lines = text.splitlines()
    if len(lines) < 2:
        errors.append(f"{path.name}: 文件为空或只有标题")
        return errors

    reader = csv.DictReader(lines)
    fieldnames = reader.fieldnames
    if not fieldnames:
        errors.append(f"{path.name}: 无法解析标题行")
        return errors

    if "id" not in fieldnames:
        errors.append(f"{path.name}: 缺少 id 列")
    if "content" not in fieldnames:
        errors.append(f"{path.name}: 缺少 content 列")

    ids = set()
    for row_num, row in enumerate(reader, start=2):
        row_id = row.get("id", "").strip()
        if not row_id:
            errors.append(f"{path.name}:L{row_num}: id 为空")
            continue
        if row_id in ids:
            errors.append(f"{path.name}:L{row_num}: id='{row_id}' 重复")
        ids.add(row_id)

        content = row.get("content", "").strip()
        if not content:
            errors.append(f"{path.name}:L{row_num}: id='{row_id}' content 为空")

        for key, val in row.items():
            if "\ufffd" in val:
                errors.append(f"{path.name}:L{row_num}: 列'{key}' 包含乱码字符")
                break

    for col in fieldnames:
        if not col.strip():
            errors.append(f"{path.name}: 存在空列标题")
            break

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate Codex Writer references CSV files.")
    parser.add_argument("--references-dir", type=Path, default=Path(__file__).resolve().parent.parent / "references" / "csv")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--log-path", type=Path, default=None)
    parser.add_argument("--no-log", action="store_true")
    args = parser.parse_args()

    references_dir = args.references_dir
    if not references_dir.exists():
        payload = {
            "ok": False,
            "csv_count": 0,
            "error_count": 1,
            "errors": [f"references/csv 目录不存在: {references_dir}"],
            "files": [],
        }
        _emit(payload, args.format)
        sys.exit(1)

    csv_files = list(references_dir.glob("*.csv"))
    if not csv_files:
        payload = {
            "ok": False,
            "csv_count": 0,
            "error_count": 1,
            "errors": ["没有找到 CSV 文件"],
            "files": [],
        }
        _emit(payload, args.format)
        sys.exit(1)

    all_errors = []
    for csv_path in sorted(csv_files):
        errs = validate_csv(csv_path)
        if errs:
            all_errors.extend(errs)

    if all_errors:
        payload = _build_payload(csv_files, False, all_errors)
        _emit(payload, args.format)
        if not args.no_log and args.log_path:
            _log_result(args.log_path, csv_files, False, all_errors)
        sys.exit(1)
    else:
        payload = _build_payload(csv_files, True, [])
        _emit(payload, args.format)
        if not args.no_log and args.log_path:
            _log_result(args.log_path, csv_files, True, [])
        sys.exit(0)


def _build_payload(csv_files: list, passed: bool, errors: list) -> dict:
    return {
        "ok": passed,
        "csv_count": len(csv_files),
        "error_count": len(errors),
        "errors": errors,
        "files": [f.name for f in csv_files],
    }


def _emit(payload: dict, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False))
        return
    if payload["ok"]:
        print(f"校验通过: {payload['csv_count']} 个 CSV 文件，0 个错误")
    else:
        print(f"校验失败: {payload['error_count']} 个错误")
        for e in payload["errors"]:
            print(f"  - {e}")


def _log_result(log_path: Path, csv_files: list, passed: bool, errors: list) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "time": datetime.now(timezone.utc).isoformat(),
        "csv_count": len(csv_files),
        "passed": passed,
        "error_count": len(errors),
        "errors": errors[:20],
        "files": [f.name for f in csv_files]
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
