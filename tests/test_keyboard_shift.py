import sys
from unittest.mock import patch, call

sys.path.append('.')
sys.path.append('./src')

from horizon6_autogear.shifting.keyboard import KeyboardOutput


def test_upshift_with_clutch():
    with patch('horizon6_autogear.shifting.keyboard.pressdown_str') as mock_down, \
         patch('horizon6_autogear.shifting.keyboard.release_str') as mock_up, \
         patch('horizon6_autogear.shifting.keyboard.press_str') as mock_press, \
         patch('horizon6_autogear.shifting.keyboard.time') as mock_time:
        kb = KeyboardOutput(clutch_enabled=True)
        kb.execute_shift('up')
        assert mock_down.mock_calls == [call('i')]
        assert mock_press.mock_calls == [call('e')]
        assert mock_up.mock_calls == [call('i')]
        assert mock_time.sleep.call_count == 2
        mock_time.sleep.assert_any_call(0)
        mock_time.sleep.assert_any_call(0.06)


def test_upshift_without_clutch():
    with patch('horizon6_autogear.shifting.keyboard.pressdown_str') as mock_down, \
         patch('horizon6_autogear.shifting.keyboard.release_str') as mock_up, \
         patch('horizon6_autogear.shifting.keyboard.press_str') as mock_press, \
         patch('horizon6_autogear.shifting.keyboard.time') as mock_time:
        kb = KeyboardOutput(clutch_enabled=False)
        kb.execute_shift('up')
        mock_down.assert_not_called()
        assert mock_press.mock_calls == [call('e')]
        mock_up.assert_not_called()
        assert mock_time.sleep.call_count == 2


def test_downshift_with_clutch_no_farming():
    with patch('horizon6_autogear.shifting.keyboard.pressdown_str') as mock_down, \
         patch('horizon6_autogear.shifting.keyboard.release_str') as mock_up, \
         patch('horizon6_autogear.shifting.keyboard.press_str') as mock_press, \
         patch('horizon6_autogear.shifting.keyboard.time') as mock_time:
        kb = KeyboardOutput(clutch_enabled=True, farming=False)
        kb.execute_shift('down')
        assert mock_down.mock_calls == [call('i'), call('w')]
        assert mock_up.mock_calls == [call('w'), call('i')]
        assert mock_press.mock_calls == [call('q')]
        assert mock_time.sleep.call_count == 3
        mock_time.sleep.assert_any_call(0.12)
        mock_time.sleep.assert_any_call(0)


def test_downshift_with_clutch_farming():
    with patch('horizon6_autogear.shifting.keyboard.pressdown_str') as mock_down, \
         patch('horizon6_autogear.shifting.keyboard.release_str') as mock_up, \
         patch('horizon6_autogear.shifting.keyboard.press_str') as mock_press, \
         patch('horizon6_autogear.shifting.keyboard.time') as mock_time:
        kb = KeyboardOutput(clutch_enabled=True, farming=True)
        kb.execute_shift('down')
        assert mock_down.mock_calls == [call('i')]
        assert mock_up.mock_calls == [call('i')]
        assert mock_press.mock_calls == [call('q')]
        assert call(0.12) not in mock_time.sleep.mock_calls
        mock_time.sleep.assert_any_call(0)
        mock_time.sleep.assert_any_call(0.06)


def test_downshift_without_clutch():
    with patch('horizon6_autogear.shifting.keyboard.pressdown_str') as mock_down, \
         patch('horizon6_autogear.shifting.keyboard.release_str') as mock_up, \
         patch('horizon6_autogear.shifting.keyboard.press_str') as mock_press, \
         patch('horizon6_autogear.shifting.keyboard.time') as mock_time:
        kb = KeyboardOutput(clutch_enabled=False)
        kb.execute_shift('down')
        mock_down.assert_not_called()
        assert mock_press.mock_calls == [call('q')]
        mock_up.assert_not_called()
        assert mock_time.sleep.call_count == 2
