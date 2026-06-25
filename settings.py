import json
import sys
from pathlib import Path

from constants import (
    DEFAULT_INST_IDS,
    INSTRUMENT_TYPES,
    MAX_INSTRUMENTS,
    SETTINGS_DEFAULTS,
)


def normalize_inst_ids(inst_ids):
    result = []
    for inst_id in inst_ids or []:
        if not isinstance(inst_id, str):
            continue
        normalized = inst_id.strip().upper()
        if not normalized or normalized in result:
            continue
        result.append(normalized)
        if len(result) >= MAX_INSTRUMENTS:
            break
    return result or list(DEFAULT_INST_IDS)


def guess_inst_type(inst_id):
    if inst_id.endswith("-SWAP"):
        return "SWAP"
    parts = inst_id.split("-")
    if len(parts) >= 3:
        return "FUTURES"
    return "SPOT"


def normalize_instruments(instruments, fallback_inst_ids=None):
    result = []
    seen = set()
    for instrument in instruments or []:
        if not isinstance(instrument, dict):
            continue
        inst_id = str(instrument.get("instId") or "").strip().upper()
        inst_type = str(instrument.get("instType") or "").strip().upper()
        if not inst_id or inst_id in seen:
            continue
        if inst_type not in INSTRUMENT_TYPES:
            inst_type = guess_inst_type(inst_id)
        result.append({"instId": inst_id, "instType": inst_type})
        seen.add(inst_id)
        if len(result) >= MAX_INSTRUMENTS:
            break

    if result:
        return result

    fallback = []
    for inst_id in normalize_inst_ids(fallback_inst_ids):
        fallback.append({"instId": inst_id, "instType": guess_inst_type(inst_id)})
    return fallback[:MAX_INSTRUMENTS]


def ensure_instruments(value):
    if value and all(isinstance(item, dict) for item in value):
        return normalize_instruments(value)
    return normalize_instruments(None, value)


def settings_path():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).with_name("OKX_Price_settings.json")
    return Path(__file__).with_name("OKX_Price_settings.json")


def load_settings():
    settings = json.loads(json.dumps(SETTINGS_DEFAULTS))
    path = settings_path()
    if not path.exists():
        return settings
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return settings

    for key, default in SETTINGS_DEFAULTS.items():
        value = data.get(key)
        if key == "instruments":
            settings[key] = normalize_instruments(value, data.get("inst_ids"))
        elif key == "alpha":
            try:
                settings[key] = min(1.0, max(0.35, float(value)))
            except (TypeError, ValueError):
                settings[key] = default
        elif isinstance(value, str) and value.startswith("#") and len(value) == 7:
            settings[key] = value
    return settings


def save_settings(settings):
    path = settings_path()
    data = {key: settings[key] for key in SETTINGS_DEFAULTS}
    try:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass
