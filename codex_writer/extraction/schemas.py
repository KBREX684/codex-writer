EXTRACTION_SCHEMA_VERSION = "codex-writer/extraction-result/v1"


def validate_extraction_result(data: dict) -> list[str]:
    errors = []
    meta = data.get("meta", {})
    if meta.get("schema_version") != EXTRACTION_SCHEMA_VERSION:
        errors.append("meta.schema_version 不正确: " + str(meta.get("schema_version")))
    if not isinstance(data.get("chapter"), int):
        errors.append("chapter 必须是整数")
    if not isinstance(data.get("accepted_events"), list):
        errors.append("accepted_events 必须是数组")
    if not isinstance(data.get("summary_text"), str):
        errors.append("summary_text 必须是字符串")
    if not isinstance(data.get("covered_nodes"), list):
        errors.append("covered_nodes 必须是数组")
    if not isinstance(data.get("missed_nodes"), list):
        errors.append("missed_nodes 必须是数组")
    if not isinstance(data.get("pending_disambiguation"), list):
        errors.append("pending_disambiguation 必须是数组")
    if not isinstance(data.get("state_deltas"), list):
        errors.append("state_deltas 必须是数组")
    if not isinstance(data.get("entity_deltas"), list):
        errors.append("entity_deltas 必须是数组")
    if not isinstance(data.get("scenes"), list):
        errors.append("scenes 必须是数组")
    if not isinstance(data.get("dominant_thread"), str):
        errors.append("dominant_thread 必须是字符串")
    if not isinstance(data.get("entities_appeared"), list):
        errors.append("entities_appeared 必须是数组")
    return errors
