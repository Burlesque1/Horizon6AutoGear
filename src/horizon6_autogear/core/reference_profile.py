"""Reference lap profile parser for Horizon6AutoGear.

Parses telemetry recordings into reference lap profiles containing
normalized ReferencePoint frames extracted from the best lap.
"""

from dataclasses import dataclass, field
import json
import os
import gzip
import statistics

from horizon6_autogear.core.forza_data_packet import ForzaDataPacket


@dataclass
class ReferencePoint:
    """A single frame of reference lap telemetry data."""
    dist: float           # dist_traveled (meters)
    lap_no: int
    pos_x: float
    pos_y: float
    pos_z: float
    speed: float          # m/s
    rpm: float
    gear: int
    steer: float          # normalized -1.0 to 1.0 (signed int8 -> val/128)
    throttle: float       # normalized 0.0-1.0 (raw 0-255 -> val/255)
    brake: float          # normalized 0.0-1.0 (raw 0-255 -> val/255)
    yaw: float
    avg_slip: float       # (tire_combined_slip_FL + FR + RL + RR) / 4
    timestamp: float      # cur_lap_time


@dataclass
class ReferenceProfile:
    """A complete reference lap profile with metadata and frames."""
    metadata: dict
    frames: list          # list of ReferencePoint
    segments: dict = field(default_factory=dict)  # brake_zones, shift_points (populated later)

    @staticmethod
    def from_recording(recording_path: str, packet_format: str = 'fh6') -> 'ReferenceProfile':
        """Parse a recording file into a reference profile.

        Handles gzip-compressed .f6rec.json files.
        Detects lap boundaries via lap_no changes.
        Selects best lap (lowest avg slip + best lap time).
        """
        data = _load_recording(recording_path)
        packets_raw = data['packets']
        metadata = data.get('metadata', {})

        # Reconstruct ForzaDataPackets from hex bytes
        fdps = []
        for pkt in packets_raw:
            # Packets may be dicts {'dt': float, 'hex': str} or plain hex strings
            hex_str = pkt['hex'] if isinstance(pkt, dict) else pkt
            raw_bytes = bytes.fromhex(hex_str)
            fdp = ForzaDataPacket(raw_bytes, packet_format=packet_format)
            if fdp.is_race_on:
                fdps.append(fdp)

        if not fdps:
            raise ValueError("No valid packets in recording")

        # Detect lap boundaries via lap_no changes
        laps = _split_laps(fdps)

        if not laps:
            # No lap boundary found -- use all data as single lap
            laps = [fdps]

        # Select best lap
        best_lap = _select_best_lap(laps)

        # Extract ReferencePoints from best lap
        frames = [_fdp_to_reference_point(fdp) for fdp in best_lap]

        # Compute metadata
        lap_time = frames[-1].timestamp - frames[0].timestamp if len(frames) > 1 else 0
        total_distance = frames[-1].dist - frames[0].dist if len(frames) > 1 else 0

        profile_metadata = {
            'car_ordinal': fdps[0].car_ordinal,
            'car_class': fdps[0].car_class,
            'car_performance_index': fdps[0].car_performance_index,
            'drivetrain_type': fdps[0].drivetrain_type,
            'track_name': metadata.get('track_name', ''),
            'lap_time': round(lap_time, 3),
            'total_distance': round(total_distance, 1),
            'frame_count': len(frames),
            'sample_rate': metadata.get('sample_rate', 60),
            'source': os.path.basename(recording_path),
        }

        profile = ReferenceProfile(metadata=profile_metadata, frames=frames)
        profile.extract_brake_zones()
        profile.extract_shift_points()
        return profile

    def extract_brake_zones(self, threshold: float = 0.1):
        """Find contiguous frames where brake > threshold.

        Returns list of dicts: {start_dist, end_dist, max_brake, severity}.
        Severity: light if max_brake < 0.4, medium if 0.4-0.7, heavy if > 0.7.
        """
        zones = []
        in_zone = False
        zone_start = 0.0
        max_brake = 0.0

        for i, frame in enumerate(self.frames):
            if frame.brake > threshold:
                if not in_zone:
                    in_zone = True
                    zone_start = frame.dist
                    max_brake = frame.brake
                else:
                    if frame.brake > max_brake:
                        max_brake = frame.brake
            else:
                if in_zone:
                    zones.append(_brake_zone(zone_start, self.frames[i - 1].dist, max_brake))
                    in_zone = False
                    max_brake = 0.0

        if in_zone:
            zones.append(_brake_zone(zone_start, self.frames[-1].dist, max_brake))

        self.segments['brake_zones'] = zones
        return zones

    def extract_shift_points(self):
        """Find gear changes between consecutive frames.

        Returns list of dicts: {dist, from_gear, to_gear, type}.
        type is 'up' if to_gear > from_gear, 'down' otherwise.
        """
        points = []
        for i in range(1, len(self.frames)):
            prev_gear = self.frames[i - 1].gear
            curr_gear = self.frames[i].gear
            if curr_gear != prev_gear:
                points.append({
                    'dist': round(self.frames[i].dist, 2),
                    'from_gear': prev_gear,
                    'to_gear': curr_gear,
                    'type': 'up' if curr_gear > prev_gear else 'down',
                })

        self.segments['shift_points'] = points
        return points

    def save(self, path: str):
        """Save reference profile to JSON file."""
        dirpath = os.path.dirname(path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        data = {
            'metadata': self.metadata,
            'segments': self.segments,
            'frames': [
                {
                    'dist': round(f.dist, 2),
                    'pos_x': round(f.pos_x, 2),
                    'pos_y': round(f.pos_y, 2),
                    'pos_z': round(f.pos_z, 2),
                    'speed': round(f.speed, 3),
                    'rpm': round(f.rpm, 0),
                    'gear': f.gear,
                    'steer': round(f.steer, 3),
                    'throttle': round(f.throttle, 3),
                    'brake': round(f.brake, 3),
                    'yaw': round(f.yaw, 4),
                    'avg_slip': round(f.avg_slip, 4),
                }
                for f in self.frames
            ]
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load(path: str) -> 'ReferenceProfile':
        """Load reference profile from JSON file."""
        with open(path, 'r') as f:
            data = json.load(f)

        frames = [
            ReferencePoint(
                dist=fr['dist'],
                lap_no=0,
                pos_x=fr['pos_x'],
                pos_y=fr['pos_y'],
                pos_z=fr['pos_z'],
                speed=fr['speed'],
                rpm=fr['rpm'],
                gear=fr['gear'],
                steer=fr['steer'],
                throttle=fr['throttle'],
                brake=fr['brake'],
                yaw=fr['yaw'],
                avg_slip=fr['avg_slip'],
                timestamp=0,
            )
            for fr in data['frames']
        ]

        return ReferenceProfile(
            metadata=data['metadata'],
            frames=frames,
            segments=data.get('segments', {}),
        )


def _brake_severity(max_brake: float) -> str:
    if max_brake < 0.4:
        return 'light'
    elif max_brake <= 0.7:
        return 'medium'
    return 'heavy'


def _brake_zone(start_dist: float, end_dist: float, max_brake: float) -> dict:
    return {
        'start_dist': round(start_dist, 2),
        'end_dist': round(end_dist, 2),
        'max_brake': round(max_brake, 3),
        'severity': _brake_severity(max_brake),
    }


def _load_recording(path: str) -> dict:
    """Load recording JSON, auto-detecting gzip or plain."""
    with open(path, 'rb') as f:
        header = f.read(2)
        f.seek(0)
        if header[:2] == b'\x1f\x8b':
            with gzip.open(f, 'rt', encoding='utf-8') as gf:
                return json.load(gf)
        else:
            return json.loads(f.read().decode('utf-8'))


def _fdp_to_reference_point(fdp) -> ReferencePoint:
    """Convert ForzaDataPacket to ReferencePoint with normalized values."""
    avg_slip = (fdp.tire_combined_slip_FL + fdp.tire_combined_slip_FR +
                fdp.tire_combined_slip_RL + fdp.tire_combined_slip_RR) / 4.0
    return ReferencePoint(
        dist=fdp.dist_traveled,
        lap_no=fdp.lap_no,
        pos_x=fdp.position_x,
        pos_y=fdp.position_y,
        pos_z=fdp.position_z,
        speed=fdp.speed,
        rpm=fdp.current_engine_rpm,
        gear=fdp.gear,
        steer=fdp.steer / 128.0,
        throttle=fdp.accel / 255.0,
        brake=fdp.brake / 255.0,
        yaw=fdp.yaw,
        avg_slip=avg_slip,
        timestamp=fdp.cur_lap_time,
    )


def _split_laps(fdps: list) -> list:
    """Split FDPs into individual laps based on lap_no changes.

    Returns list of lists, each inner list is one lap.
    Ignores the first partial segment (before first lap boundary).
    """
    laps = []
    current_lap = [fdps[0]]
    current_lap_no = fdps[0].lap_no

    for fdp in fdps[1:]:
        if fdp.lap_no != current_lap_no:
            # Lap boundary detected
            if fdp.lap_no > current_lap_no:
                laps.append(current_lap)
            current_lap = [fdp]
            current_lap_no = fdp.lap_no
        else:
            current_lap.append(fdp)

    # Don't forget the last lap
    if current_lap:
        laps.append(current_lap)

    return laps


def _select_best_lap(laps: list) -> list:
    """Select the best lap from available laps.

    Criteria: lowest average slip + best lap time.
    Score = avg_slip + lap_time / 100.0
    """
    if len(laps) == 1:
        return laps[0]

    scored = []
    for lap in laps:
        if len(lap) < 10:
            continue
        avg_slip = statistics.mean([
            (fdp.tire_combined_slip_FL + fdp.tire_combined_slip_FR +
             fdp.tire_combined_slip_RL + fdp.tire_combined_slip_RR) / 4.0
            for fdp in lap
        ])
        lap_time = lap[-1].cur_lap_time - lap[0].cur_lap_time
        if lap_time <= 0:
            continue
        scored.append((avg_slip, lap_time, lap))

    if not scored:
        return laps[0]

    # Pick lowest combined score (normalized)
    best = min(scored, key=lambda x: x[0] + x[1] / 100.0)
    return best[2]
