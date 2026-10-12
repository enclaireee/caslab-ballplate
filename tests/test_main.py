import csv
import time

import pytest

from laptop import main


def test_parse_command_ok():
    assert main.parse_command("sp 50 0") == ("setpoint", {"x_mm": 50.0, "y_mm": 0.0})
    assert main.parse_command("gains both 0.4 0 0.3") == (
        "pid_gains", {"axis": "both", "kp": 0.4, "ki": 0.0, "kd": 0.3})
    assert main.parse_command("quit") == ("quit", None)
    assert main.parse_command("   ") is None


@pytest.mark.parametrize("line", ["sp 50", "sp a b", "sp 999 0", "gains z 1 0 0", "gains x -1 0 0", "hello"])
def test_parse_command_bad(line):
    with pytest.raises(ValueError):
        main.parse_command(line)


def test_no_vision_without_mock_exits(capsys):
    assert main.main([]) == 2
    assert "belum tersedia" in capsys.readouterr().err


def test_mock_run_fills_csv(tmp_path):
    def lines():
        yield "sp 30 0\n"
        yield "oops\n"  # input salah tidak boleh crash
        yield "gains both 0.4 0 0.3\n"
        time.sleep(1.0)
        yield "quit\n"

    out = tmp_path / "demo.csv"
    assert main.main(["--mock", "--csv", str(out)], stdin=lines()) == 0
    rows = list(csv.DictReader(out.open()))
    assert len(rows) > 10
    assert any(float(r["sp_x_mm"]) == 30.0 for r in rows)
