from codex_writer.memory.scratchpad import (
    bootstrap, update_from_commit, add_learn_entry, query_memory, get_memory_stats, get_active_loops
)


def test_bootstrap_creates_scratchpad(tmp_path):
    (tmp_path / ".codex-writer").mkdir()
    (tmp_path / ".codex-writer" / "memory.json").write_text('{"open_loops": [], "long_term_facts": []}', encoding="utf-8")
    data = bootstrap(tmp_path)
    assert (tmp_path / ".codex-writer" / "memory_scratchpad.json").exists()
    assert "episodic" in data
    assert "semantic" in data


def test_update_from_commit_adds_events(tmp_path):
    (tmp_path / ".codex-writer").mkdir()
    bootstrap(tmp_path)
    commit = {
        "meta": {"status": "accepted", "chapter": 1},
        "accepted_events": [{"event_id": "ev-1", "chapter": 1, "event_type": "entity_mentioned", "subject": "萧衡", "payload": {}}],
        "summary_text": "test summary"
    }
    update_from_commit(tmp_path, 1, commit)
    stats = get_memory_stats(tmp_path)
    assert stats["episodic_total"] >= 2


def test_learn_entry_adds_to_episodic(tmp_path):
    (tmp_path / ".codex-writer").mkdir()
    bootstrap(tmp_path)
    add_learn_entry(tmp_path, "主角性格暴躁但讲义气", tag="character", chapter=3)
    results = query_memory(tmp_path, tag="character")
    assert len(results) == 1
    assert results[0]["type"] == "author_note"


def test_active_loops_filters_correctly(tmp_path):
    (tmp_path / ".codex-writer").mkdir()
    bootstrap(tmp_path)
    commit = {
        "meta": {"status": "accepted", "chapter": 1},
        "accepted_events": [
            {"event_id": "loop-1", "chapter": 1, "event_type": "open_loop_created", "subject": "青铜令", "payload": {}}
        ],
        "summary_text": ""
    }
    update_from_commit(tmp_path, 1, commit)
    loops = get_active_loops(tmp_path)
    assert len(loops) >= 1
