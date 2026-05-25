"""Playback source for replaying recorded UDP data.

Uses duck typing: implements recvfrom() so it can be passed to helper.nextFdp()
as a drop-in replacement for a real UDP socket.
"""

import gzip
import hashlib
import json
import time


class PlaybackSource:
    """Replays recorded UDP packets with original timing.

    Implements recvfrom() for duck-typing compatibility with helper.nextFdp().
    Playback mode never sends key presses — pure data display + algorithm verification.
    """

    def __init__(self, recording_path: str):
        self.data = self._load_json(recording_path)

        self.metadata = self.data['metadata']
        self.packets = self.data['packets']
        self.index = 0
        self.start_time = None
        self.packet_format = self.metadata.get('format', 'fh6')

        # Integrity checks
        self._validate()

    @staticmethod
    def _load_json(recording_path: str) -> dict:
        """Load recording JSON, auto-detecting gzip or plain format."""
        # Read raw bytes to detect gzip magic number (0x1f 0x8b)
        with open(recording_path, 'rb') as f:
            header = f.read(2)
            f.seek(0)
            if header[:2] == b'\x1f\x8b':
                with gzip.open(f, 'rt', encoding='utf-8') as gf:
                    return json.load(gf)
            else:
                return json.loads(f.read().decode('utf-8'))

    def _validate(self):
        """Validate recording data integrity.

        Checks packet count and sha256 hash (if present in metadata).
        Raises ValueError on failure.
        """
        actual_count = len(self.packets)
        expected_count = self.metadata.get('packet_count')
        if expected_count is not None and actual_count != expected_count:
            raise ValueError(
                f'Packet count mismatch: metadata says {expected_count}, file has {actual_count}'
            )

        # Verify sha256 hash if present (v2 recordings)
        expected_hash = self.metadata.get('sha256')
        if expected_hash:
            hasher = hashlib.sha256()
            for pkt in self.packets:
                hex_str = pkt['hex']
                hasher.update(len(hex_str).to_bytes(4, 'big'))
                hasher.update(hex_str.encode('ascii'))
            actual_hash = hasher.hexdigest()
            if actual_hash != expected_hash:
                raise ValueError(
                    'SHA256 mismatch: data may be corrupted'
                )

    def recvfrom(self, bufsize):
        """Mimic socket.recvfrom(). Returns (bytes, address).

        Uses time compensation to prevent drift.
        Returns (None, None) at end of recording.
        """
        if self.index >= len(self.packets):
            return None, None

        packet = self.packets[self.index]

        if self.start_time is None:
            self.start_time = time.monotonic()

        # Compensate for time.sleep() drift on Windows
        target_elapsed = packet['dt']
        actual_elapsed = time.monotonic() - self.start_time
        sleep_time = target_elapsed - actual_elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

        self.index += 1
        return bytes.fromhex(packet['hex']), ('playback', 0)

    @property
    def progress(self):
        """Return playback progress as (current, total)."""
        return self.index, len(self.packets)

    @property
    def is_finished(self):
        return self.index >= len(self.packets)

    @staticmethod
    def load_metadata(recording_path: str) -> dict:
        """Load only metadata from a recording file (lightweight)."""
        data = PlaybackSource._load_json(recording_path)
        return data.get('metadata', {})
