import json
import os
import tempfile
from unittest.mock import MagicMock
from concurrent.futures import ThreadPoolExecutor

from horizon6_autogear.core.forza import Forza
from horizon6_autogear.utils import helper
from horizon6_autogear.config import config as constants


def test_tcs_params_round_trip():
    """TCS params survive save -> load cycle."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pool = MagicMock(spec=ThreadPoolExecutor)
        pool.submit = MagicMock()

        # Create engine with custom config folder
        engine1 = Forza(pool, packet_format='fh6')
        engine1.config_folder = tmpdir
        engine1.tcs_enabled = False
        engine1.traction_controller.slip_threshold = 1.2
        engine1.traction_controller.throttle_reduction = 0.5
        engine1.traction_controller.recovery_threshold = 1.2 - 0.2  # margin=0.2

        # Save
        helper.dump_settings(engine1)

        # Verify file exists
        path = os.path.join(tmpdir, 'settings.json')
        assert os.path.exists(path)

        # Load into fresh engine
        engine2 = Forza(pool, packet_format='fh6')
        engine2.config_folder = tmpdir
        # load_settings was already called in __init__ via helper.load_settings(self)
        # But config_folder was set after __init__, so reload
        helper.load_settings(engine2)

        # After __init__, TractionController is created with defaults
        # Then load_settings stores _saved_* attrs
        # We need to manually apply (normally done in __init__ after TC creation)
        if hasattr(engine2, '_saved_tcs_enabled'):
            engine2.tcs_enabled = engine2._saved_tcs_enabled
        if hasattr(engine2, '_saved_tcs_slip_threshold'):
            engine2.traction_controller.slip_threshold = engine2._saved_tcs_slip_threshold
        if hasattr(engine2, '_saved_tcs_throttle_reduction'):
            engine2.traction_controller.throttle_reduction = engine2._saved_tcs_throttle_reduction
        if hasattr(engine2, '_saved_tcs_recovery_margin'):
            engine2.traction_controller.recovery_threshold = engine2.traction_controller.slip_threshold - engine2._saved_tcs_recovery_margin

        assert engine2.tcs_enabled is False
        assert engine2.traction_controller.slip_threshold == 1.2
        assert engine2.traction_controller.throttle_reduction == 0.5
        assert abs(engine2.traction_controller.recovery_threshold - 1.0) < 0.001


def test_tcs_defaults_when_no_settings_file():
    """TCS defaults are used when no settings file exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pool = MagicMock(spec=ThreadPoolExecutor)
        engine = Forza(pool, packet_format='fh6')
        engine.config_folder = tmpdir
        # No settings file -- defaults should be unchanged
        assert engine.tcs_enabled == constants.TCS_ENABLED
        assert engine.traction_controller.slip_threshold == constants.TCS_SLIP_THRESHOLD
        assert engine.traction_controller.throttle_reduction == constants.TCS_THROTTLE_REDUCTION


def test_settings_json_contains_tcs_keys():
    """dump_settings writes all TCS keys to JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pool = MagicMock(spec=ThreadPoolExecutor)
        pool.submit = MagicMock()
        engine = Forza(pool, packet_format='fh6')
        engine.config_folder = tmpdir
        helper.dump_settings(engine)

        path = os.path.join(tmpdir, 'settings.json')
        with open(path) as f:
            data = json.load(f)

        assert 'tcs_enabled' in data
        assert 'tcs_slip_threshold' in data
        assert 'tcs_throttle_reduction' in data
        assert 'tcs_recovery_margin' in data
