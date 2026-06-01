import sys
import os
import threading
import time

sys.path.append(r'.')
sys.path.append(r'./src')

from horizon6_autogear.shifting.output_device import OutputDevice, CommandedState, SharedState
from horizon6_autogear.shifting.simulated_output import SimulatedOutput


def test_commanded_state_defaults():
    state = CommandedState()
    assert state.throttle == 1.0
    assert state.brake == 0.0


def test_commanded_state_custom():
    state = CommandedState(throttle=0.5, brake=0.3)
    assert state.throttle == 0.5
    assert state.brake == 0.3


def test_shared_state_shift_pending():
    state = SharedState()
    assert not state.shift_pending.is_set()
    state.shift_pending.set()
    assert state.shift_pending.is_set()
    state.shift_pending.clear()
    assert not state.shift_pending.is_set()


def test_simulated_output_set_analog():
    output = SimulatedOutput()
    output.set_analog('throttle', 0.8)
    output.set_analog('brake', 0.4)
    assert len(output.log) == 2
    assert output.log[0][1] == 'throttle'
    assert abs(output.log[0][2] - 0.8) < 0.01
    assert output.log[1][1] == 'brake'
    assert abs(output.log[1][2] - 0.4) < 0.01


def test_simulated_output_execute_shift():
    output = SimulatedOutput()
    output.execute_shift('up')
    output.execute_shift('down')
    assert len(output.log) == 2
    assert output.log[0][1] == 'shift'
    assert output.log[0][2] == 'up'
    assert output.log[1][2] == 'down'


def test_simulated_output_clear():
    output = SimulatedOutput()
    output.set_analog('throttle', 0.5)
    assert len(output.log) == 1
    output.clear()
    assert len(output.log) == 0


from unittest.mock import patch, MagicMock


def test_keyboard_output_press_above_threshold():
    with patch('horizon6_autogear.shifting.keyboard.pressdown_str') as mock_down, \
         patch('horizon6_autogear.shifting.keyboard.release_str') as mock_up:
        from horizon6_autogear.shifting.keyboard import KeyboardOutput
        kb = KeyboardOutput()
        kb.set_analog('throttle', 0.8)
        mock_down.assert_called_once_with('w')
        mock_up.assert_not_called()


def test_keyboard_output_release_below_threshold():
    with patch('horizon6_autogear.shifting.keyboard.pressdown_str') as mock_down, \
         patch('horizon6_autogear.shifting.keyboard.release_str') as mock_up:
        from horizon6_autogear.shifting.keyboard import KeyboardOutput
        kb = KeyboardOutput()
        kb._throttle_pressed = True
        kb.set_analog('throttle', 0.05)
        mock_up.assert_called_once_with('w')
        mock_down.assert_not_called()


def test_keyboard_output_no_op_when_state_unchanged():
    with patch('horizon6_autogear.shifting.keyboard.pressdown_str') as mock_down, \
         patch('horizon6_autogear.shifting.keyboard.release_str') as mock_up:
        from horizon6_autogear.shifting.keyboard import KeyboardOutput
        kb = KeyboardOutput()
        kb._throttle_pressed = True
        kb.set_analog('throttle', 0.9)
        mock_down.assert_not_called()
        mock_up.assert_not_called()


def test_keyboard_output_brake():
    with patch('horizon6_autogear.shifting.keyboard.pressdown_str') as mock_down, \
         patch('horizon6_autogear.shifting.keyboard.release_str') as mock_up:
        from horizon6_autogear.shifting.keyboard import KeyboardOutput
        kb = KeyboardOutput()
        kb.set_analog('brake', 0.5)
        mock_down.assert_called_once_with('s')
        mock_up.assert_not_called()
