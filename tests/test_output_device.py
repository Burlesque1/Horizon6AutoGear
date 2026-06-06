import sys
from unittest.mock import MagicMock, patch

sys.path.append(r'.')
sys.path.append(r'./src')

from horizon6_autogear.shifting.output_device import CommandedState, SharedState
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


def test_simulated_analog_log():
    output = SimulatedOutput()
    output.set_analog('throttle', 0.8)
    output.set_analog('brake', 0.3)
    assert len(output.analog_log) == 2
    assert output.analog_log[0][1] == 'throttle'
    assert abs(output.analog_log[0][2] - 0.8) < 0.01
    assert output.analog_log[1][1] == 'brake'
    assert abs(output.analog_log[1][2] - 0.3) < 0.01


def test_simulated_shift_log():
    output = SimulatedOutput()
    output.execute_shift('up')
    output.execute_shift('down')
    assert len(output.shift_log) == 2
    assert output.shift_log[0][1] == 'up'
    assert output.shift_log[1][1] == 'down'


def test_simulated_snapshot():
    output = SimulatedOutput()
    output.set_analog('throttle', 0.8)
    output.set_analog('brake', 0.3)
    snapshot = output.get_analog_snapshot()
    assert snapshot == {'throttle': 0.8, 'brake': 0.3}


def test_simulated_last_values():
    output = SimulatedOutput()
    output.set_analog('throttle', 0.5)
    assert output.last_throttle == 0.5
    assert output.last_brake == 0.0
    assert output.last_steer == 0.0


def test_simulated_release_all_logged():
    output = SimulatedOutput()
    output.release_all()
    assert len(output.log) == 1
    assert output.log[0][1] == 'release_all'
    assert output.log[0][2] is None


def test_simulated_clear_resets_state():
    output = SimulatedOutput()
    output.set_analog('throttle', 0.8)
    output.execute_shift('up')
    output.clear()
    assert len(output.log) == 0
    assert len(output.analog_log) == 0
    assert len(output.shift_log) == 0
    assert output.get_analog_snapshot() == {}
    assert output.last_throttle == 0.0


def _make_mock_gamepad():
    """Create a GamepadOutput with mocked vigem_client for non-Windows testing.

    Returns a context-aware helper so the vigem_client mock stays patched
    during method calls (execute_shift references the module global).
    """
    import horizon6_autogear.shifting.virtual_gamepad as vg_mod
    mock_vc = MagicMock()
    mock_controller = MagicMock()
    mock_client = MagicMock()
    mock_client.create_x360_controller.return_value = mock_controller
    mock_vc.ViGEmBusClient.return_value = mock_client
    mock_vc.X360_AXIS = MagicMock()
    mock_vc.X360_BUTTON = MagicMock()
    original = vg_mod.vigem_client
    vg_mod.vigem_client = mock_vc
    try:
        gp = vg_mod.GamepadOutput()
    except Exception:
        vg_mod.vigem_client = original
        raise
    return gp, mock_vc, mock_controller, original


def _restore_gamepad_mock(original):
    import horizon6_autogear.shifting.virtual_gamepad as vg_mod
    vg_mod.vigem_client = original


def test_gamepad_execute_shift_up_clutch_sequence():
    gp, mock_vc, mock_ctrl, original = _make_mock_gamepad()
    try:
        gp.execute_shift('up')
        assert mock_ctrl.press_button.call_args_list[0][0][0] == mock_vc.X360_BUTTON.LEFT_SHOULDER
        assert mock_ctrl.press_button.call_args_list[1][0][0] == mock_vc.X360_BUTTON.B
        assert mock_ctrl.release_button.call_args_list[0][0][0] == mock_vc.X360_BUTTON.B
        assert mock_ctrl.release_button.call_args_list[1][0][0] == mock_vc.X360_BUTTON.LEFT_SHOULDER
    finally:
        _restore_gamepad_mock(original)


def test_gamepad_execute_shift_down_clutch_sequence():
    gp, mock_vc, mock_ctrl, original = _make_mock_gamepad()
    try:
        gp.execute_shift('down')
        assert mock_ctrl.press_button.call_args_list[0][0][0] == mock_vc.X360_BUTTON.LEFT_SHOULDER
        assert mock_ctrl.press_button.call_args_list[1][0][0] == mock_vc.X360_BUTTON.A
        assert mock_ctrl.release_button.call_args_list[0][0][0] == mock_vc.X360_BUTTON.A
        assert mock_ctrl.release_button.call_args_list[1][0][0] == mock_vc.X360_BUTTON.LEFT_SHOULDER
    finally:
        _restore_gamepad_mock(original)


def test_gamepad_set_analog_steer_noop():
    gp, _, mock_ctrl, original = _make_mock_gamepad()
    try:
        gp.set_analog('steer', 0.5)
        mock_ctrl.set_axis_value.assert_not_called()
    finally:
        _restore_gamepad_mock(original)


def test_gamepad_shifting_flag():
    gp, _, _, original = _make_mock_gamepad()
    try:
        assert not gp.shifting
        gp.execute_shift('up')
        assert not gp.shifting
    finally:
        _restore_gamepad_mock(original)
