# Phase 2: Reference Profile System — Design Spec

## Overview

Record a reference lap (manual or AI auto-drive), match the player's current position against it in real-time, and provide actionable feedback: speed delta, gear suggestion, brake point preview, and track overlay.

## Architecture

```
Recording → ReferenceProfile → PositionMatcher → FeedbackComputer → GUI/HUD
                                     ↑                    |
                              lap_dist +              speed_delta
                              pos_x/pos_z            gear_suggestion
                                                      brake_preview
                                                      track_overlay
                                                      lap_delta
```

Three core modules, each independently testable:

1. **ReferenceProfile** — parse recordings into searchable reference lap data
2. **PositionMatcher** — hybrid position matching with state machine
3. **FeedbackComputer** — compute feedback signals from matched reference

## Module 1: ReferenceProfile

### Storage Format (v1)

```json
{
  "version": 1,
  "metadata": {
    "track_name": "string (user-assigned, sanitized)",
    "car_ordinal": int,
    "car_class": int,
    "car_performance_index": int,
    "drivetrain_type": int,
    "lap_time_ms": int,
    "created_at": "ISO 8601"
  },
  "samples": [
    {
      "t": float,
      "lap_dist": float,
      "speed": float,
      "gear": int,
      "rpm": float,
      "throttle": float,
      "brake": float,
      "steer": float,
      "pos_x": float,
      "pos_y": float,
      "pos_z": float,
      "yaw": float,
      "clutch": float,
      "handbrake": float,
      "avg_slip": float
    }
  ]
}
```

Field notes:

- **`t`**: seconds from lap start (cumulative elapsed time within the lap)
- **`lap_dist`**: per-lap cumulative distance in meters (resets to 0 at lap boundary, computed from speed integration or position deltas — NOT raw `dist_traveled` which is session-total and monotonically increasing)
- **`avg_slip`**: `mean(abs(tire_combined_slip_FL), abs(tire_combined_slip_FR), abs(tire_combined_slip_RL), abs(tire_combined_slip_RR))`
- **`pos_x`, `pos_y`, `pos_z`**: raw Forza world coordinates. Ground plane is `(pos_x, pos_z)`; `pos_y` is vertical (height)
- 16 fields per sample, supports Phase 3/4 auto-drive
- Metadata field names match `ForzaDataPacket` attribute names (`car_performance_index`, `drivetrain_type`)
- File: `data/profiles/{sanitized_track_name}_{car_ordinal}_{timestamp}.json`
- Version field enables future migration (follow existing config v1→v2 pattern)

### Downsampling

Raw telemetry at 60Hz produces ~7200 samples per 2-min lap. Reference profiles are resampled to **fixed 1-meter distance intervals**:

- Average lap at 150 km/h covers ~5 km → ~5000 samples
- Each sample represents equal track distance, not equal time
- Makes position matching predictable: scan N samples = scan N meters
- LOST state full scan of 5000 samples fits easily in <10ms
- Low-speed sections (hairpins) naturally get denser sampling per meter

### Lap Boundary Detection

Dual-signal algorithm:

1. `lap_no` increment → mark candidate boundary
2. `cur_lap_time` drops to near-zero (< 0.5s) → confirm boundary
3. Both signals present → valid boundary
4. Only one signal → reject as noise

Note: `dist_traveled` is NOT used for lap detection — it is a session-total monotonically increasing value that does not reset between laps in Forza Horizon.

### Cleanest Lap Selection

When a recording contains multiple laps, select the best by:

1. Lowest variance in `avg_slip` (smoothest driving)
2. Fewest position jumps (no crashes/respawns — detect via `pos_x/pos_z` delta > 50m between consecutive frames)
3. Best `cur_lap_time`

### Profile Management

- User manually assigns track name when saving (sanitized: alphanumeric + underscore + hyphen, max 64 chars)
- Profiles listed by track_name + car info
- Car change invalidates active profile — checks all four fields matching `__update_forza_info` logic: `car_ordinal`, `car_performance_index`, `car_class`, `drivetrain_type`
- Profile loader validates version field, migrates older formats
- Reject profiles with < 1 detected lap
- Reject recording if packet format is `sled` (missing position/brake fields)

### Recording Workflow

1. User clicks "Record Reference" → system begins recording telemetry
2. User drives 2-3 laps
3. User clicks "Stop Recording"
4. System detects lap boundaries, selects cleanest lap
5. System prompts user to name the track
6. Profile is resampled to 1m intervals and saved

## Module 2: PositionMatcher

### Coordinate Convention

Forza world coordinates: `pos_x` = lateral, `pos_z` = forward/backward (ground plane), `pos_y` = vertical (height). All 2D matching uses **`(pos_x, pos_z)`** — the horizontal ground plane. The vertical axis `pos_y` is excluded from distance calculations to avoid penalizing elevation changes on hilly tracks.

### State Machine

```
MATCHED ──(lap_dist jump >100m or no match in window)──→ SCANNING
  ↑                               |
  |                          (match found,
  |                           confidence high)
  |                               |
  └───────────────────────────────┘
  ↑                               |
  |                          (no confident match)
  |                               v
  └────(re-localize success)── LOST
                                   |
                              (show "reference lost"
                               in GUI, suppress feedback)
```

### MATCHED State (normal driving)

Sequential locality scan from `last_index`:

1. Forward window ±50 samples from `last_index` (±50m at 1m/sample)
2. Filter by `lap_dist` proximity (±20m)
3. Among candidates, pick minimum 2D Euclidean distance on `(pos_x, pos_z)`
4. Update `last_index`
5. O(1) amortized, <1ms per frame

### SCANNING State (position discontinuity)

1. Expand window to ±500 samples (±500m)
2. Search by 2D Euclidean distance `(pos_x, pos_z)`
3. If best distance < 5m → transition to MATCHED after confirmation
4. If no good match → LOST

### LOST State (full re-localization)

1. Full O(n) scan of all ~5000 samples by 2D position `(pos_x, pos_z)`
2. Find closest sample within 10m
3. **Confirmation step**: verify next 5 consecutive frames also match sequentially before accepting
4. If confirmed → MATCHED; otherwise remain LOST
5. GUI shows "reference lost" indicator, all feedback suppressed

Confirmation prevents snapping to a geometrically close but logically wrong track section (e.g., hairpin exit near a straight).

### Thread Safety

- `last_index` and state owned by telemetry worker thread
- Feedback output uses **double-buffering**: worker writes to a new `Feedback` object, then atomically swaps the reference pointer. GUI always reads from the stable reference
- Under CPython's GIL, a single pointer assignment is atomic — no torn reads
- GUI never reads partially-constructed feedback

## Module 3: FeedbackComputer

### Speed Delta

```
speed_delta = current_speed - reference.speed  (km/h)
positive = faster than reference, negative = slower
```

Note: Convention is positive=faster (opposite to Forza's `norm_ai_brake_diff` where negative=ahead). The GUI must display this unambiguously with color coding (green=faster, red=slower).

### Gear Suggestion

```
suggested_gear = reference.gear at matched position
display when: suggested_gear != current_gear
```

### Brake Preview

Speed-adaptive scan-ahead:

```
scan_ahead_meters = current_speed_kmh / 3.6 * preview_seconds
preview_seconds = REF_PROFILE_PREVIEW_SECONDS = 3.0  (new constant in config.py)
brake_threshold = REF_PROFILE_BRAKE_THRESHOLD = 10    (new constant: brake > 10/255 ≈ 4% pressed)
```

- Scan forward from matched index within `scan_ahead_meters`
- Find first sample where `reference.brake > REF_PROFILE_BRAKE_THRESHOLD`
- Return distance-to-brake and reference brake intensity
- At 300km/h: scans ~250m (3s), at 150km/h: scans ~125m (3s)
- Constant warning time, not constant distance
- This supplements (does not replace) the Phase 1 `norm_ai_brake_diff` signal

### Track Overlay

- Reference trajectory: draw all `(pos_x, pos_z)` from profile on track map
- Current trajectory: existing live track data
- Both rendered on the same canvas with different colors

### Lap Time Delta

```
lap_delta = cur_lap_time - reference.t[matched_index]
```

Uses the `t` field (elapsed seconds from lap start) stored per reference sample. No per-frame accumulation needed — direct time comparison at matched position.

### Output Type

```python
@dataclass
class Feedback:
    state: str  # "valid" | "unavailable"
    speed_delta: float | None       # km/h, positive = faster
    gear_suggestion: int | None     # reference gear at matched position
    brake_distance_m: float | None  # meters to next brake zone
    brake_intensity: float | None   # reference brake value (0-255)
    matched_index: int | None       # index in reference profile
    lap_delta_s: float | None       # seconds, positive = slower
```

When `state == "unavailable"`, all numeric fields are None and GUI shows "reference lost".

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Recording has 0 laps | Reject, show error "No complete lap detected" |
| Recording has 1 lap | Use that lap (no cleanest selection needed) |
| Profile file corrupted / invalid JSON | Reject on load, show error in profile selector |
| `pos_x/pos_z` are all zero (car not spawned) | Skip matching until valid position arrives |
| Wrong packet format (`sled`) | Reject recording, show "Requires FH5/FH6 data format" |
| Car changed mid-session | Invalidate active profile, show warning to select new profile |

## Integration

### Forza.run() Insertion Point

```
__update_forza_info()          # car change detection → invalidate profile
         ↓
position_matcher.match(fdp)    # find reference point
         ↓
feedback_computer.compute(match_result, fdp)  # compute feedback
         ↓
shifting()                     # gear suggestion can influence shift decisions
```

### Web GUI (Phantom Theme)

- Settings panel: profile selector dropdown, save/delete controls
- Track map: reference trajectory overlay (dashed line, different color)
- Speed delta: live chart or numeric display (green=faster, red=slower)
- Brake preview: marker on track map ahead of current position
- Gear suggestion: indicator next to current gear display
- Lap delta: timer-style display showing +/- seconds

### HUD Overlay (Tkinter)

- Speed delta bar (horizontal, center = on pace, green = ahead, red = behind)
- Gear suggestion text (e.g., "→ 3" next to current gear)
- Brake countdown (distance or time to next brake point)
- "Reference lost" indicator when matcher state is LOST

## User Workflow

1. **Record**: Click "Record Reference" → drive 2-3 laps → click "Stop" → name the track → save
2. **Select**: Choose a saved profile from the profile selector
3. **Drive**: System matches position in real-time at 60Hz
4. **Feedback**: See speed delta, gear suggestions, brake previews, track overlay
5. **Compare**: Review lap delta at session end

## New Constants (config.py)

```python
REF_PROFILE_PREVIEW_SECONDS = 3.0      # brake preview look-ahead time
REF_PROFILE_BRAKE_THRESHOLD = 10       # brake > 10/255 = ~4% pressed
REF_PROFILE_SCAN_WINDOW_NORMAL = 50    # ±50 samples (±50m) for MATCHED state
REF_PROFILE_SCAN_WINDOW_WIDE = 500     # ±500 samples for SCANNING state
REF_PROFILE_RELOCALIZE_RADIUS = 10.0   # max meters for LOST re-localization
REF_PROFILE_CONFIRM_FRAMES = 5         # frames to confirm re-localization
```

## Future Compatibility

- ReferenceProfile v1 format includes all 16 fields needed for Phase 3 (semi-auto) and Phase 4 (full-auto)
- FeedbackComputer output maps directly to PID control inputs in Phase 3
- PositionMatcher state machine extends naturally to auto-drive control loop
- No schema migration needed for Phase 3/4
