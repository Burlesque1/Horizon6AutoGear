"""Tests for profile_matcher module — hybrid position matching algorithm."""

import os
from types import SimpleNamespace

import pytest

from horizon6_autogear.core.reference_profile import (
    ReferencePoint,
    ReferenceProfile,
)
from horizon6_autogear.core.profile_matcher import ProfileMatcher


RECORDING_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'data2', 'recordings', '20260517_235830.f6rec.json'
)


def _make_profile(n=100, start_x=0.0, step_x=1.0):
    """Build a synthetic ReferenceProfile with n frames spaced along X axis."""
    frames = [
        ReferencePoint(
            dist=i * 10.0, lap_no=1,
            pos_x=start_x + i * step_x, pos_y=0.0, pos_z=0.0,
            speed=50.0, rpm=5000, gear=3,
            steer=0.0, throttle=0.8, brake=0.0,
            yaw=0.0, avg_slip=0.1, timestamp=i * 0.016,
        )
        for i in range(n)
    ]
    return ReferenceProfile(metadata={'frame_count': n}, frames=frames)


def _make_fdp(pos_x=0.0, pos_y=0.0, pos_z=0.0, dist_traveled=0.0):
    """Build a minimal FDP-like object for matcher input."""
    return SimpleNamespace(
        position_x=pos_x,
        position_y=pos_y,
        position_z=pos_z,
        dist_traveled=dist_traveled,
    )


class TestInitialization:
    """Test ProfileMatcher initial state."""

    def test_initial_state(self):
        """Matcher starts uninitialized with last_index 0."""
        profile = _make_profile()
        matcher = ProfileMatcher(profile)
        assert matcher.last_index == 0
        assert matcher.prev_dist == 0.0
        assert matcher.initialized is False

    def test_empty_profile(self):
        """ProfileMatcher with empty frames returns None on match."""
        profile = ReferenceProfile(metadata={}, frames=[])
        matcher = ProfileMatcher(profile)
        fdp = _make_fdp()
        result, idx = matcher.match(fdp)
        assert result is None
        assert idx == 0


class TestFirstMatchRelocalization:
    """Test that the first match triggers full relocalization."""

    def test_first_match_returns_result(self):
        """First match should find the closest reference point."""
        profile = _make_profile(n=50, start_x=100.0)
        matcher = ProfileMatcher(profile)
        fdp = _make_fdp(pos_x=105.0, pos_y=0.0, pos_z=0.0, dist_traveled=50.0)
        result, idx = matcher.match(fdp)
        assert result is not None
        assert isinstance(result, ReferencePoint)
        assert matcher.initialized is True

    def test_first_match_finds_closest(self):
        """First match should find the frame closest to given position."""
        profile = _make_profile(n=50, start_x=0.0, step_x=10.0)
        matcher = ProfileMatcher(profile)
        fdp = _make_fdp(pos_x=25.0, pos_y=0.0, pos_z=0.0, dist_traveled=250.0)
        result, idx = matcher.match(fdp)
        assert result is not None
        assert idx == 2  # frame at x=20 is closest to x=25 (dist_sq=25), vs x=30 (dist_sq=25); tiebreak -> lower index
        # Actually both idx 2 (x=20) and idx 3 (x=30) have dist_sq 25. First found wins -> idx 2.


class TestSequentialMatching:
    """Test that sequential matching produces monotonically non-decreasing indices."""

    def test_indices_monotonic(self):
        """Feeding positions in order should produce non-decreasing indices."""
        profile = _make_profile(n=100, start_x=0.0, step_x=1.0)
        matcher = ProfileMatcher(profile)

        indices = []
        for i in range(80):
            fdp = _make_fdp(
                pos_x=float(i) + 0.1,
                pos_y=0.0,
                pos_z=0.0,
                dist_traveled=float(i) * 10.0,
            )
            result, idx = matcher.match(fdp)
            assert result is not None
            indices.append(idx)

        assert all(indices[i] <= indices[i + 1] for i in range(len(indices) - 1))

    def test_sequential_matches_nearby(self):
        """Sequential match should find a frame close to the input position."""
        profile = _make_profile(n=100, start_x=0.0, step_x=1.0)
        matcher = ProfileMatcher(profile)

        for i in range(50):
            fdp = _make_fdp(
                pos_x=float(i) + 0.05,
                pos_y=0.0,
                pos_z=0.0,
                dist_traveled=float(i) * 10.0,
            )
            result, idx = matcher.match(fdp)

        assert result is not None
        assert abs(result.pos_x - 49.0) < 2.0


class TestDiscontinuityHandling:
    """Test that dist_traveled discontinuity triggers relocalization."""

    def test_discontinuity_triggers_relocalize(self):
        """Large negative dist_traveled delta triggers full relocalization."""
        profile = _make_profile(n=100, start_x=0.0, step_x=1.0)
        matcher = ProfileMatcher(profile)

        for i in range(10):
            fdp = _make_fdp(
                pos_x=float(i),
                pos_y=0.0,
                pos_z=0.0,
                dist_traveled=float(i) * 10.0,
            )
            matcher.match(fdp)

        assert matcher.initialized is True
        assert matcher.last_index == 9

        # Simulate lap reset: dist jumps back to near 0, position near frame 5
        jump_fdp = _make_fdp(pos_x=5.0, pos_y=0.0, pos_z=0.0, dist_traveled=5.0)
        result, idx = matcher.match(jump_fdp)

        assert result is not None
        assert idx == 5

    def test_small_negative_delta_no_relocalize(self):
        """Small negative dist delta should NOT trigger relocalization."""
        profile = _make_profile(n=100, start_x=0.0, step_x=1.0)
        matcher = ProfileMatcher(profile)

        for i in range(10):
            fdp = _make_fdp(
                pos_x=float(i),
                pos_y=0.0,
                pos_z=0.0,
                dist_traveled=100.0 + float(i) * 10.0,
            )
            matcher.match(fdp)

        # Small negative delta (-5m) is above threshold (-50m)
        small_neg_fdp = _make_fdp(
            pos_x=10.0, pos_y=0.0, pos_z=0.0,
            dist_traveled=100.0 + 9 * 10.0 - 5.0,
        )
        result, idx = matcher.match(small_neg_fdp)
        assert result is not None


class TestMatchFailure:
    """Test that matching returns None for positions far from all reference points."""

    def test_far_position_returns_none(self):
        """Position far from all reference frames returns None."""
        profile = _make_profile(n=50, start_x=0.0, step_x=1.0)
        matcher = ProfileMatcher(profile)

        # Initialize first
        fdp = _make_fdp(pos_x=5.0, pos_y=0.0, pos_z=0.0, dist_traveled=50.0)
        matcher.match(fdp)

        # Feed a position far away (>200m from any frame)
        far_fdp = _make_fdp(
            pos_x=999999.0, pos_y=999999.0, pos_z=999999.0,
            dist_traveled=60.0,
        )
        result, idx = matcher.match(far_fdp)
        assert result is None

    def test_relocalize_far_position_returns_none(self):
        """On initialization, far position returns None."""
        profile = _make_profile(n=50, start_x=0.0, step_x=1.0)
        matcher = ProfileMatcher(profile)

        far_fdp = _make_fdp(
            pos_x=999999.0, pos_y=999999.0, pos_z=999999.0,
            dist_traveled=0.0,
        )
        result, idx = matcher.match(far_fdp)
        assert result is None


class TestReset:
    """Test that reset() clears matcher state."""

    def test_reset_clears_state(self):
        """After reset, matcher should behave like fresh initialization."""
        profile = _make_profile(n=50, start_x=0.0, step_x=1.0)
        matcher = ProfileMatcher(profile)

        for i in range(20):
            fdp = _make_fdp(
                pos_x=float(i),
                pos_y=0.0,
                pos_z=0.0,
                dist_traveled=float(i) * 10.0,
            )
            matcher.match(fdp)

        assert matcher.initialized is True
        assert matcher.last_index > 0

        matcher.reset()

        assert matcher.initialized is False
        assert matcher.last_index == 0
        assert matcher.prev_dist == 0.0

    def test_match_after_reset_works(self):
        """After reset, matching should work from scratch."""
        profile = _make_profile(n=50, start_x=0.0, step_x=1.0)
        matcher = ProfileMatcher(profile)

        for i in range(20):
            fdp = _make_fdp(
                pos_x=float(i),
                pos_y=0.0,
                pos_z=0.0,
                dist_traveled=float(i) * 10.0,
            )
            matcher.match(fdp)

        matcher.reset()

        fdp = _make_fdp(pos_x=5.0, pos_y=0.0, pos_z=0.0, dist_traveled=50.0)
        result, idx = matcher.match(fdp)
        assert result is not None
        assert matcher.initialized is True


class TestWithRealRecording:
    """Test ProfileMatcher with the real recording file."""

    @pytest.fixture
    def recording_path(self):
        """Skip test if recording file is not available."""
        path = os.path.abspath(RECORDING_PATH)
        if not os.path.exists(path):
            pytest.skip(f'Recording not found: {path}')
        return path

    @pytest.fixture
    def profile_and_fdps(self, recording_path):
        """Load profile and raw FDPs from recording."""
        from horizon6_autogear.core.forza_data_packet import ForzaDataPacket
        import json
        import gzip

        profile = ReferenceProfile.from_recording(recording_path)

        with open(recording_path, 'rb') as f:
            header = f.read(2)
            f.seek(0)
            if header[:2] == b'\x1f\x8b':
                with gzip.open(f, 'rt') as gf:
                    data = json.load(gf)
            else:
                data = json.loads(f.read().decode('utf-8'))

        fdps = []
        for pkt in data['packets']:
            raw = bytes.fromhex(pkt['hex'])
            fdp = ForzaDataPacket(raw, packet_format='fh6')
            if fdp.is_race_on:
                fdps.append(fdp)

        return profile, fdps

    def test_real_recording_first_match(self, profile_and_fdps):
        """First match on real data should return a valid reference point."""
        profile, fdps = profile_and_fdps
        matcher = ProfileMatcher(profile)
        result, idx = matcher.match(fdps[0])
        assert result is not None
        assert 0 <= idx < len(profile.frames)
        assert matcher.initialized is True

    def test_real_recording_sequential_matching(self, profile_and_fdps):
        """Sequential matching on real data should produce non-decreasing indices."""
        profile, fdps = profile_and_fdps
        matcher = ProfileMatcher(profile)

        indices = []
        for fdp in fdps[:200]:
            result, idx = matcher.match(fdp)
            if result is not None:
                indices.append(idx)

        assert len(indices) > 100
        assert all(indices[i] <= indices[i + 1] for i in range(len(indices) - 1))

    def test_real_recording_positions_close(self, profile_and_fdps):
        """Matched reference points should be close to actual positions."""
        profile, fdps = profile_and_fdps
        matcher = ProfileMatcher(profile)

        max_position_error = 0.0
        for fdp in fdps[:200]:
            result, idx = matcher.match(fdp)
            if result is not None:
                error = (
                    (result.pos_x - fdp.position_x) ** 2 +
                    (result.pos_y - fdp.position_y) ** 2 +
                    (result.pos_z - fdp.position_z) ** 2
                ) ** 0.5
                max_position_error = max(max_position_error, error)

        assert max_position_error < 10.0, f'Max position error {max_position_error:.1f}m too large'
