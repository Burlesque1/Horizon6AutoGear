"""Recorder for saving raw UDP packets for later playback.

Saves raw hex bytes + relative timestamps. Raw hex can reconstruct
full ForzaDataPacket with all 85 fields — no data loss.
"""

import gzip
import hashlib
import json
import os
import time
from datetime import datetime


class Recorder:
    """Records raw UDP bytes for later playback.

    Usage:
        rec = Recorder(output_dir="data/recordings")
        # ... in data loop:
        rec.record(raw_bytes)
        # ... when done:
        path = rec.save(metadata={"format": "fh6", "car_ordinal": 42})
    """

    def __init__(self, output_dir: str, expected_packet_size: int = None):
        self.output_dir = output_dir
        self.packets = []
        self.start_time = None
        self.expected_packet_size = expected_packet_size
        self.skipped_count = 0
        os.makedirs(self.output_dir, exist_ok=True)

    def record(self, raw_bytes: bytes):
        """Record a single raw UDP packet.

        Skips packets with unexpected size and increments skipped_count.
        """
        if self.expected_packet_size and len(raw_bytes) != self.expected_packet_size:
            self.skipped_count += 1
            return

        if self.start_time is None:
            self.start_time = time.monotonic()
        self.packets.append({
            'dt': round(time.monotonic() - self.start_time, 4),
            'hex': raw_bytes.hex()
        })

    def save(self, metadata: dict = None) -> str:
        """Save recording to JSON file with integrity hash.

        Snapshots packets to prevent race condition with concurrent record() calls.
        Returns file path. Raises ValueError if no valid packets.
        """
        # Snapshot to prevent race: record() may still be appending on another thread
        packets = list(self.packets)
        if not packets:
            raise ValueError('No packets recorded')

        # Compute hash over all packet hex strings for integrity check
        hasher = hashlib.sha256()
        for pkt in packets:
            hex_str = pkt['hex']
            hasher.update(len(hex_str).to_bytes(4, 'big'))
            hasher.update(hex_str.encode('ascii'))

        duration = packets[-1]['dt']
        now = datetime.now()
        meta = {
            'format': metadata.get('format', 'fh6') if metadata else 'fh6',
            'version': 2,
            'packet_count': len(packets),
            'skipped_count': self.skipped_count,
            'duration_sec': round(duration, 2),
            'recorded_at': now.isoformat(),
            'sha256': hasher.hexdigest(),
        }
        if metadata:
            for key in ('car_ordinal', 'car_class', 'car_drivetrain'):
                if key in metadata:
                    meta[key] = metadata[key]

        timestamp = now.strftime('%Y%m%d_%H%M%S')
        filename = f'{timestamp}.f6rec.json'
        filepath = os.path.join(self.output_dir, filename)

        raw_json = json.dumps({
            'metadata': meta,
            'packets': packets,
        }, ensure_ascii=False).encode('utf-8')

        with gzip.open(filepath, 'wb') as f:
            f.write(raw_json)

        return filepath

    @property
    def packet_count(self):
        return len(self.packets)
