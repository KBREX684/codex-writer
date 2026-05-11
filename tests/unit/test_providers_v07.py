from codex_writer.agents.providers import parse_json_content


def test_parse_json_content_accepts_fenced_json():
    payload = parse_json_content('```json\n{"chapter": 1, "title": "Entry"}\n```')
    assert payload == {"chapter": 1, "title": "Entry"}


def test_parse_json_content_returns_empty_dict_for_plain_prose():
    assert parse_json_content("Chapter prose without JSON") == {}
