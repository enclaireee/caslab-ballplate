import pytest

from contracts.validate import ContractError, validate

VALID = {
    "ball_position": {"t_ms": 1200, "x_mm": 12.5, "y_mm": -3.0, "valid": True},
    "setpoint": {"x_mm": 0, "y_mm": 0},
    "pid_gains": {"axis": "both", "kp": 0.4, "ki": 0.0, "kd": 0.3},
    "telemetry": {"t_ms": 1210, "x_mm": 12.5, "y_mm": -3.0, "sp_x_mm": 0, "sp_y_mm": 0,
                  "u_x_deg": -1.2, "u_y_deg": 0.4, "valid": True},
    "vision_status": {"fps": 30.0, "latency_ms": 25.0, "ball_found": True},
}


@pytest.mark.parametrize("name", VALID)
def test_valid(name):
    assert validate(name, VALID[name]) == VALID[name]


def bad_cases():
    for n, m in VALID.items():
        k = next(iter(m))
        yield n, {x: v for x, v in m.items() if x != k}  # missing field
        yield n, {**m, k: "abc"}  # wrong type
        yield n, {**m, "extra": 1}  # unknown field
    yield "ball_position", {**VALID["ball_position"], "x_mm": 201}
    yield "ball_position", {**VALID["ball_position"], "t_ms": -1}
    yield "ball_position", {**VALID["ball_position"], "t_ms": 1.5}
    yield "ball_position", {**VALID["ball_position"], "valid": 1}
    yield "setpoint", {"x_mm": 0, "y_mm": -200.1}
    yield "pid_gains", {**VALID["pid_gains"], "axis": "z"}
    yield "pid_gains", {**VALID["pid_gains"], "kd": -0.1}
    yield "telemetry", {**VALID["telemetry"], "u_x_deg": 15.5}


@pytest.mark.parametrize("name,msg", list(bad_cases()))
def test_invalid(name, msg):
    with pytest.raises(ContractError):
        validate(name, msg)


def test_unknown_name():
    with pytest.raises(ContractError, match="unknown contract"):
        validate("nope", {})


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_rejected(bad):
    with pytest.raises(ContractError, match="non-finite"):
        validate("setpoint", {"x_mm": bad, "y_mm": 0})
