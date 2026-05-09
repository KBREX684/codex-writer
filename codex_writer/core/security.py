import re
import unicodedata


def sanitize_filename(name: str) -> str:
    name = unicodedata.normalize("NFKC", name)
    name = name.replace("\\", "").replace("/", "")
    name = re.sub(r"\.\.", "", name)
    name = re.sub(r'[\x00-\x1f\x7f<>:"|?*]', "", name)
    name = name.strip()
    if not name:
        name = "untitled"
    return name


def redact_secret(value: str) -> str:
    if not value or len(value) < 6:
        return "***"
    idx = value.find("-")
    if idx >= 0 and idx < 8:
        return value[:idx + 1] + "***"
    return value[:3] + "***"
