import re
from typing import Any, Optional


def _parse_value(value: Any) -> Any:
    """Normalize a raw evidence/threshold value into something comparable."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None

    text = str(value).strip()

    if text.lower() in ("true", "false"):
        return text.lower() == "true"

    # strip units like "%", " days", "GB" etc, keep leading number
    match = re.match(r"^-?\d+(\.\d+)?", text)
    if match:
        return float(match.group(0))

    return text  # fall back to raw string comparison (e.g. TLS version "1.3")


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    a, e = _parse_value(actual), _parse_value(expected)

    try:
        if operator == "<":
            return a < e
        if operator == "<=":
            return a <= e
        if operator == ">":
            return a > e
        if operator == ">=":
            return a >= e
        if operator == "=":
            return a == e
        if operator == "!=":
            return a != e
    except TypeError:
        # incompatible types (e.g. comparing str to float) - fall back to string equality
        return str(a) == str(e)

    return False


def compare_value(actual_value: Any, operator: str, threshold: Any) -> bool:
    """
    Public wrapper around the deterministic comparison logic. This is the ONLY
    place pass/fail is decided - used both by the legacy exact-name-match path
    and the new AI-reconciliation path, so the actual grading math is always
    deterministic and reproducible regardless of how the asset/value was found.
    """
    return _compare(actual_value, operator, threshold)


_TRUTHY_WORDS = {
    "true", "yes", "y", "enabled", "active", "elastic", "on", "automatic",
    "automated", "present", "configured", "daily", "hourly", "weekly",
    "monthly", "continuous", "scheduled",
}
_FALSY_WORDS = {
    "false", "no", "n", "disabled", "inactive", "off", "none", "manual",
    "absent", "null", "n/a", "not configured", "never", "unset",
}


def interpret_truthy(raw_value: Any) -> Optional[bool]:
    """
    Deterministic, code-level fallback for interpreting non-literal boolean
    evidence (e.g. "elastic", "daily", "none") when the AI reconciliation step
    didn't supply its own boolean_interpretation for a match. This never calls
    an LLM - it's a fixed word list, so it's fast, free, and 100% reproducible.
    Returns None (unknown) if the raw value doesn't match a known word, in
    which case the caller should fall back to raw comparison or "Not Evaluated".
    """
    if isinstance(raw_value, bool):
        return raw_value
    if raw_value is None:
        return False
    if isinstance(raw_value, (int, float)):
        return raw_value != 0
    text = str(raw_value).strip().lower()
    if text in _TRUTHY_WORDS:
        return True
    if text in _FALSY_WORDS:
        return False
    return None


def find_asset(evidence: dict, target: str) -> Optional[dict]:
    assets = evidence.get("assets", [])
    for asset in assets:
        if asset.get("name") == target:
            return asset
    return None


def evaluate_control(control, evidence: dict) -> dict:
    """
    control: object with target, metric, operator, threshold
    evidence: {"assets": [{"name": ..., "<metric>": value, ...}]}
    Returns: {"actual": str, "status": "Passed"|"Failed"|"Not Evaluated", "passed": bool|None}
    """
    asset = find_asset(evidence, control.target)
    if asset is None or control.metric not in asset:
        return {"actual": "N/A", "status": "Not Evaluated", "passed": None}

    actual_value = asset[control.metric]
    passed = _compare(actual_value, control.operator, control.threshold)

    return {
        "actual": str(actual_value),
        "status": "Passed" if passed else "Failed",
        "passed": passed,
    }