import re
from datetime import datetime, timedelta, timezone

from core.config import conf

_LEGACY_TZ_OFFSETS = {
    "Europe/Moscow": 3,
    "Europe/Kiev": 2,
    "Europe/Kyiv": 2,
    "Asia/Almaty": 6,
    "Asia/Bangkok": 7,
    "Asia/Novosibirsk": 7,
    "UTC": 0,
}


def timezone_offset_hours(value=None):
    if value is None:
        value = conf.get("TIMEZONE", 0)
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return max(-12, min(14, int(value)))
    s = str(value).strip()
    if not s:
        return 0
    if s in _LEGACY_TZ_OFFSETS:
        return _LEGACY_TZ_OFFSETS[s]
    m = re.fullmatch(r"UTC?([+-]?\d{1,2})", s, re.IGNORECASE)
    if m:
        return max(-12, min(14, int(m.group(1))))
    m = re.fullmatch(r"([+-]?\d{1,2})", s)
    if m:
        return max(-12, min(14, int(m.group(1))))
    return 0


def message_timezone():
    hours = timezone_offset_hours()
    return timezone(timedelta(hours=hours))


def timezone_combo_labels():
    return [f"UTC+{h}" if h >= 0 else f"UTC{h}" for h in range(-12, 15)]


def utc_dt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip()
        if not s:
            return None
        s = s.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            try:
                dt = datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0)


def store_message_timestamp(value):
    dt = utc_dt(value)
    if dt is None:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return dt.isoformat()


def format_message_time_local(value):
    dt = utc_dt(value)
    if dt is None:
        return ""
    return dt.astimezone(message_timezone()).strftime("%H:%M")


def remove_emojis(text: str):
    emoji_pattern = re.compile(
        "["
        "\U0001F300-\U0001FAFF"
        "\U00002700-\U000027BF"
        "\U0001F1E0-\U0001F1FF"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text)


def filter_formal(text: str):
    parts = re.split(r"(?<=[!?])", text)
    return [p for p in parts if p.strip()]


def filter_casual(text: str):
    text = re.sub(r"[^\w\s?,!?]", "", text)
    text = re.sub(r"[.\-:;]", "", text)
    parts = re.split(r"(?<=[!?])", text)
    return [p for p in parts if p.strip()]
