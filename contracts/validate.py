"""validate(name, message): check a message's `data` against contracts/<name>.json."""
import json
import math
from pathlib import Path

from jsonschema import Draft7Validator

_DIR = Path(__file__).parent
NAMES = ("ball_position", "setpoint", "pid_gains", "telemetry", "vision_status")
_validators = {n: Draft7Validator(json.loads((_DIR / f"{n}.json").read_text())) for n in NAMES}


class ContractError(ValueError):
    pass


def _check_finite(x, where):
    if isinstance(x, float) and not math.isfinite(x):
        raise ContractError(f"{where}: nilai non-finite ({x}) ditolak")
    for v in x.values() if isinstance(x, dict) else x if isinstance(x, (list, tuple)) else ():
        _check_finite(v, where)


def validate(name, message):
    v = _validators.get(name)
    if v is None:
        raise ContractError(f"unknown contract '{name}', expected one of {NAMES}")
    _check_finite(message, name)
    errs = sorted(v.iter_errors(message), key=lambda e: list(e.path))
    if errs:
        e = errs[0]
        where = ".".join(map(str, e.path)) or "<root>"
        raise ContractError(f"{name}: {where}: {e.message}")
    return message
