"""Integration tests for reference profile system in Forza engine and GUI."""

import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

from horizon6_autogear.core.forza import Forza
from horizon6_autogear.core.reference_profile import ReferenceProfile


RECORDING_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'data2', 'recordings', '20260517_235830.f6rec.json'
)


def _make_engine():
    pool = MagicMock(spec=ThreadPoolExecutor)
    pool.submit = MagicMock()
    engine = Forza(pool, packet_format='fh6')
    engine.shift_point = {2: {'rpm': 6500}, 3: {'rpm': 6500}}
    engine.minGear = 1
    engine.maxGear = 10
    engine._init_shift_controller()
    return engine


def test_load_unload_reference_profile():
    engine = _make_engine()
    assert engine.reference_profile is None
    assert engine.profile_matcher is None

    profile = ReferenceProfile.from_recording(RECORDING_PATH)
    with tempfile.NamedTemporaryFile(suffix='.ref.json', delete=False, mode='w') as f:
        path = f.name
    profile.save(path)

    engine.load_reference_profile(path)
    assert engine.reference_profile is not None
    assert engine.profile_matcher is not None
    assert len(engine.reference_profile.frames) > 0

    engine.unload_reference_profile()
    assert engine.reference_profile is None
    assert engine.profile_matcher is None

    os.unlink(path)


def test_compute_reference_data_returns_dict():
    engine = _make_engine()
    profile = ReferenceProfile.from_recording(RECORDING_PATH)
    with tempfile.NamedTemporaryFile(suffix='.ref.json', delete=False, mode='w') as f:
        path = f.name
    profile.save(path)
    engine.load_reference_profile(path)

    fdp = MagicMock()
    fdp.position_x = profile.frames[0].pos_x
    fdp.position_y = profile.frames[0].pos_y
    fdp.position_z = profile.frames[0].pos_z
    fdp.dist_traveled = profile.frames[0].dist
    fdp.speed = profile.frames[0].speed
    fdp.gear = profile.frames[0].gear

    result = engine._compute_reference_data(fdp)
    assert result is not None
    assert 'speed_diff' in result
    assert 'gear_suggestion' in result
    assert 'lap_progress' in result
    assert 'next_brake_point' in result

    os.unlink(path)


def test_compute_reference_data_none_without_profile():
    engine = _make_engine()
    fdp = MagicMock()
    result = engine._compute_reference_data(fdp)
    assert result is None


def test_compute_reference_data_match_failure():
    engine = _make_engine()
    profile = ReferenceProfile.from_recording(RECORDING_PATH)
    with tempfile.NamedTemporaryFile(suffix='.ref.json', delete=False, mode='w') as f:
        path = f.name
    profile.save(path)
    engine.load_reference_profile(path)

    fdp = MagicMock()
    fdp.position_x = 999999
    fdp.position_y = 999999
    fdp.position_z = 999999
    fdp.dist_traveled = 999999
    fdp.speed = 0
    fdp.gear = 3

    result = engine._compute_reference_data(fdp)
    assert result is None

    os.unlink(path)
