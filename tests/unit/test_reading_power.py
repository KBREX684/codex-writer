from codex_writer.reading_power.tracker import (
    add_debt, pay_debt, expire_old_debts, get_open_debts, get_debt_summary, detect_hooks_from_text
)


def test_add_and_pay_debt_cycle(tmp_path):
    (tmp_path / ".codex-writer").mkdir()
    add_debt(tmp_path, 1, "\u9752\u94dc\u4ee4\u7684\u79d8\u5bc6", "hook")
    assert len(get_open_debts(tmp_path)) == 1
    pay_debt(tmp_path, "debt-ch0001-001")
    assert len(get_open_debts(tmp_path)) == 0


def test_expire_old_debts(tmp_path):
    (tmp_path / ".codex-writer").mkdir()
    add_debt(tmp_path, 1, "old debt")
    expired = expire_old_debts(tmp_path, 15, window=10)
    assert expired == 1
    assert len(get_open_debts(tmp_path)) == 0


def test_debt_summary_counts_correctly(tmp_path):
    (tmp_path / ".codex-writer").mkdir()
    add_debt(tmp_path, 1, "debt1")
    add_debt(tmp_path, 2, "debt2")
    pay_debt(tmp_path, "debt-ch0001-001")
    summary = get_debt_summary(tmp_path)
    assert summary["total"] == 2
    assert summary["open"] == 1
    assert summary["paid"] == 1


def test_detect_hooks_short_text_returns_empty():
    hooks = detect_hooks_from_text("\u77ed\u6587\u672c\u3002", 1)
    assert isinstance(hooks, list)
