import pytest
from horizon6_autogear.widgets.hud_overlay import (
    normalize_driving_line,
    brake_indicator_state,
    tire_grip_state,
)


def test_normalize_driving_line_center():
    assert normalize_driving_line(0) == 0.0


def test_normalize_driving_line_max_right():
    assert normalize_driving_line(127) == pytest.approx(1.0)


def test_normalize_driving_line_max_left():
    assert normalize_driving_line(-128) == pytest.approx(-128 / 127, abs=0.01)


def test_normalize_driving_line_half():
    assert normalize_driving_line(64) == pytest.approx(64 / 127, abs=0.01)


def test_brake_green():
    assert brake_indicator_state(0) == 'green'
    assert brake_indicator_state(50) == 'green'
    assert brake_indicator_state(1) == 'green'


def test_brake_yellow():
    assert brake_indicator_state(-50) == 'yellow'
    assert brake_indicator_state(-80) == 'yellow'


def test_brake_red():
    assert brake_indicator_state(-81) == 'red'
    assert brake_indicator_state(-127) == 'red'


def test_tire_green():
    assert tire_grip_state(0.0) == 'green'
    assert tire_grip_state(0.49) == 'green'


def test_tire_yellow():
    assert tire_grip_state(0.5) == 'yellow'
    assert tire_grip_state(0.79) == 'yellow'


def test_tire_red():
    assert tire_grip_state(0.8) == 'red'
    assert tire_grip_state(2.0) == 'red'
