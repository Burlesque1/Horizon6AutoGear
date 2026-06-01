# Virtual Gamepad + TCS + Corner Control — Design Spec

## Summary

Add virtual gamepad output (ViGEmBus), traction control (TCS), and corner throttle/brake auto-control to Horizon6AutoGear. Uses a two-tier control architecture: a fast tier (TCS, corner control, never blocks) and an action tier (gear shifts, may block). Controllers are independently testable via recording playback on macOS.

## Motivation

The current system only controls gear shifts via keyboard (binary on/off). This limits control precision — no proportional throttle or brake modulation is possible. Adding a virtual gamepad enables:

- **TCS (traction control)**: Detect wheel slip from telemetry and reduce throttle proportionally, preventing wheelspin
- **Corner control**: Auto-modulate throttle and brake through corners based on steering angle, slip, and driving line
- **Smooth shifts**: Gamepad can do analog clutch/throttle during shifts instead of binary key presses

## Architecture

### Two-Tier Control

```
forza.py run() loop (~60Hz, single thread)
       |
       v
  ForzaDataPacket
       |
       v
  Shared State (thread-safe)
  ├── latest_fdp: ForzaDataPacket
  ├── commanded: CommandedState
  └── shift_pending: threading.Event
       |
       +---> [Fast Tier — inline, <5ms budget]
       |     TractionController → tcs_throttle
       |     CornerController → corner_throttle, corner_brake
       |     Arbiter → resolves conflicts → CommandedState
       |     OutputDevice.set_analog() → instant
       |
       +---> [Action Tier — threadPool]
             ShiftController → check shift_pending → execute shift → clear flag
```

### Module Layout

```
shifting/                    Shift algorithm + output hardware
├── output_device.py         OutputDevice protocol + CommandedState dataclass
├── keyboard.py              KeyboardOutput (refactored, preserves platform guards)
├── virtual_gamepad.py       GamepadOutput (ViGEmBus, Windows-only)
├── simulated_output.py      SimulatedOutput (test mock, logs actions)
├── gear_helper.py           Shift algorithm (analysis + decision logic, unchanged)
└── shift_controller.py      ShiftController (decision + async execution wrapper)

control/                     Runtime controllers
├── traction_controller.py   TCS (slip detection → throttle reduction)
├── corner_controller.py     Corner (steer/slip → throttle/brake modulation)
└── arbiter.py               Output conflict resolution

core/                        Data models + parsing only (unchanged)
```

**Rule**: `shifting/` owns shift algorithm and all output hardware. `control/` owns real-time control logic that reads telemetry and computes desired outputs. `core/` remains data models + parsing only.

## OutputDevice Protocol

### Interface

```python
class OutputDevice(Protocol):
    def set_analog(self, channel: str, value: float): ...
    def execute_shift(self, direction: str): ...

class CommandedState:
    throttle: float   # 0.0 to 1.0
    brake: float      # 0.0 to 1.0
```

- Controllers always output float [0.0, 1.0]
- Each OutputDevice implementation handles translation
- `channel` values: `'throttle'`, `'brake'`

### KeyboardOutput

Threshold-based binary press/release. Stateful — tracks whether each key is currently pressed.

```python
class KeyboardOutput:
    THROTTLE_THRESHOLD = 0.1

    def set_analog(self, channel, value):
        if channel == 'throttle':
            if value > THROTTLE_THRESHOLD and not self._throttle_pressed:
                pressdown_str(ACCELERATION)
                self._throttle_pressed = True
            elif value <= THROTTLE_THRESHOLD and self._throttle_pressed:
                release_str(ACCELERATION)
                self._throttle_pressed = False
```

**Limitation**: TCS with keyboard produces on/off throttle cuts (jerky but functional). Proportional TCS requires GamepadOutput.

### GamepadOutput

Direct analog values, instant dispatch. Windows-only via ViGEmBus.

```python
class GamepadOutput:
    def set_analog(self, channel, value):
        if channel == 'throttle':
            self._controller.set_throttle(value)
        elif channel == 'brake':
            self._controller.set_brake(value)
```

Platform guard follows existing `keyboard.py` pattern:
```python
if sys.platform == 'win32':
    import vigem_client
else:
    vigem_client = None
```

### SimulatedOutput

Test mock. Logs every action for assertion in tests.

```python
class SimulatedOutput:
    def set_analog(self, channel, value):
        self.log.append((time.monotonic(), channel, value))

    def execute_shift(self, direction):
        self.log.append((time.monotonic(), 'shift', direction))
```

## Double-Shift Prevention (CRITICAL-1)

Belt-and-suspenders approach:

1. **Structural guard**: `shift_pending` threading.Event. Set atomically before submitting to threadPool. Cleared in `finally` block of worker function.
2. **Temporal guard**: Existing `last_upshift` / `last_downshift` cooldown timestamps (350ms). Kept as rate-limiter.

```python
if shift_controller.should_shift(fdp):
    if not shared_state.shift_pending.is_set():
        shared_state.shift_pending.set()
        threadPool.submit(shift_controller.execute_shift, gear, shared_state)

def execute_shift(self, gear, shared_state):
    try:
        if gear < self.max_gear:
            up_shift_handle(gear, self.output_device)
    finally:
        shared_state.shift_pending.clear()
```

The main loop is single-threaded, so the check-then-set is safe. Only the main thread checks and sets the Event; the worker thread only clears it.

## Arbiter: Output Conflict Resolution (CRITICAL-2)

Resolves throttle/brake conflicts between controllers. Safety-first: lowest-wins for throttle.

```python
class Arbiter:
    def resolve(self, driver_throttle, tcs_throttle, corner_throttle,
                corner_brake, shift_pending):
        if shift_pending:
            return CommandedState(
                throttle=driver_throttle,
                brake=0.0
            )
        return CommandedState(
            throttle=min(driver_throttle, tcs_throttle, corner_throttle),
            brake=corner_brake
        )
```

**Shift-in-progress behavior**: When `shift_pending` is set, TCS is suppressed (drivetrain is disconnected via clutch, so TCS modulation is useless). Driver throttle passes through unchanged.

**`driver_throttle` semantics**: `fdp.accel / 255.0` (ForzaDataPacket reports throttle as 0-255 integer). During farming, effectively 1.0 (keyboard always pressed).

**Optional controller outputs**: When a controller is not yet implemented (e.g., CornerController in Phase 2), its output defaults to pass-through: `corner_throttle=1.0`, `corner_brake=0.0`.

## Timing Budget

```
Per-iteration at 60Hz (16.7ms total):
  socket.recvfrom():     ~2ms (UDP already buffered by OS)
  __update_forza_info(): ~0.5ms (exception: 5-50ms on car change, not a regression)
  TractionController:    ~1ms (threshold comparison)
  CornerController:      ~1ms (steer + slip lookup)
  Arbiter:               ~0.2ms (min + conditional)
  OutputDevice dispatch: ~0.3ms (in-memory write or Win32 call)
  Total target:          <5ms (11.7ms margin)

Monitoring: warn if any iteration > 12ms. Error if 3 consecutive warnings.
Exception: car-change file I/O spike is pre-existing, excluded from warning counter.
```

## TractionController (TCS)

### Inputs (from ForzaDataPacket)

| Field | Purpose |
|-------|---------|
| `tire_slip_ratio_RL/RR` | Rear wheel longitudinal slip (drive wheels for RWD/AWD) |
| `tire_slip_ratio_FL/FR` | Front wheel longitudinal slip (drive wheels for FWD) |
| `tire_combined_slip_RL/RR` | Rear wheel combined slip |
| `tire_combined_slip_FL/FR` | Front wheel combined slip |
| `drivetrain_type` | 0=FWD, 1=RWD, 2=AWD — determines which wheels to monitor |
| `speed` | Vehicle speed (ignore TCS below minimum threshold) |
| `accel` | Current throttle input |

### Algorithm

```python
class TractionController:
    SLIP_THRESHOLD = 0.5       # combined_slip above this triggers intervention
    MIN_SPEED = 5.0            # m/s, don't intervene below this
    THROTTLE_REDUCTION = 0.3   # reduce to this fraction of driver throttle

    def compute(self, fdp) -> float:
        """Returns target throttle (0.0-1.0). 1.0 = no intervention."""
        if fdp.speed < self.MIN_SPEED:
            return 1.0

        if fdp.drivetrain_type == 1:    # RWD
            drive_slip = max(fdp.tire_combined_slip_RL, fdp.tire_combined_slip_RR)
        elif fdp.drivetrain_type == 0:  # FWD
            drive_slip = max(fdp.tire_combined_slip_FL, fdp.tire_combined_slip_FR)
        else:                            # AWD
            drive_slip = max(fdp.tire_combined_slip_FL, fdp.tire_combined_slip_FR,
                             fdp.tire_combined_slip_RL, fdp.tire_combined_slip_RR)

        if drive_slip > self.SLIP_THRESHOLD:
            return self.THROTTLE_REDUCTION
        return 1.0
```

**Tuning**: SLIP_THRESHOLD and THROTTLE_REDUCTION will be configurable via config.py and adjustable in the GUI. Initial values based on Forza telemetry analysis — combined_slip > 0.5 indicates significant wheelspin.

## CornerController

### Inputs

| Field | Purpose |
|-------|---------|
| `steer` | Steering input (-1.0 to 1.0) |
| `yaw` | Vehicle yaw angle |
| `norm_driving_line` | Game-computed driving line deviation (0=center, -1=inside, 1=outside) |
| `tire_combined_slip_FL/FR/RL/RR` | Per-wheel combined slip |
| `speed` | Vehicle speed |

### Algorithm (Phase 3 — placeholder for Phase 1-2)

```python
class CornerController:
    STEER_THRESHOLD = 0.3      # steering above this = in a corner
    SLIP_LIMIT = 0.4           # combined_slip above this = too much speed

    def compute(self, fdp) -> tuple[float, float]:
        """Returns (corner_throttle, corner_brake)."""
        if abs(fdp.steer) < self.STEER_THRESHOLD:
            return 1.0, 0.0    # straight, no intervention

        max_slip = max(fdp.tire_combined_slip_FL, fdp.tire_combined_slip_FR,
                       fdp.tire_combined_slip_RL, fdp.tire_combined_slip_RR)

        if max_slip > self.SLIP_LIMIT:
            return 0.7, 0.0    # reduce throttle, no brake

        return 1.0, 0.0        # corner but under control
```

## Farming Acceleration (MAJOR from Critic)

Farming acceleration key management stays **outside** the OutputDevice protocol. The existing pattern in `forza.py:448-449` continues unchanged:

```python
if not display_only and self.farming:
    keyboard_helper.pressdown_str(constants.ACCELERATION)  # start of run
    # ...
    keyboard_helper.release_str(constants.ACCELERATION)    # end of run
```

Farming mode uses the keyboard directly for persistent key holds. TCS modulation during farming with keyboard is a no-op (can't partially press a key). When GamepadOutput is active, farming acceleration can be managed via `set_analog('throttle', 1.0)`.

## forza.py Changes (SIGINIFICANT)

### run() Method Restructure

Before (simplified):
```python
while self.isRunning:
    fdp = nextFdp(socket, format, recorder)
    update_car_gui_func(fdp)
    __update_forza_info(fdp)
    if not display_only:
        __exp_farming_setup(fdp)
        shifting(iteration, fdp)
```

After (simplified):
```python
while self.isRunning:
    fdp = nextFdp(socket, format, recorder)
    update_car_gui_func(fdp)
    __update_forza_info(fdp)
    if not display_only:
        __exp_farming_setup(fdp)
        shared_state.latest_fdp = fdp

        if not shared_state.shift_pending.is_set():
            tcs_throttle = traction_controller.compute(fdp)
            corner_throttle, corner_brake = corner_controller.compute(fdp)
            driver_throttle = fdp.accel / 255.0

            commanded = arbiter.resolve(
                driver_throttle, tcs_throttle, corner_throttle,
                corner_brake, shared_state.shift_pending.is_set()
            )
            output_device.set_analog('throttle', commanded.throttle)
            output_device.set_analog('brake', commanded.brake)

        if shift_controller.should_shift(fdp):
            if not shared_state.shift_pending.is_set():
                shared_state.shift_pending.set()
                threadPool.submit(
                    shift_controller.execute_shift,
                    fdp.gear, shared_state
                )
```

### shifting() Method

**DECOMPOSED and REMOVED.** Slip computation moves to TractionController. Shift decision logic moves to ShiftController. The 64-line method (forza.py:298-362) is replaced by controller calls in run().

### Unchanged Methods

- `__update_forza_info()` — config auto-loading
- `test_gear()` — data collection
- `analyze()` — shift point calculation
- `create_socket()` / socket management
- `run_playback()` — uses SimulatedOutput for testing

## Graceful Degradation

| Scenario | Behavior |
|----------|----------|
| ViGEmBus not installed | GUI shows "Gamepad unavailable", falls back to KeyboardOutput |
| TCS causing issues | User disables via GUI toggle (same pattern as clutch/farm toggles) |
| Output device swap at runtime | Atomic reference swap on toggle, no lock needed (single writer in run loop) |
| Emergency stop | Esc or GUI close sets `isRunning=False`, all output stops immediately |
| Rollback | Disable TCS/corner control toggles to revert to current behavior |

## Test Strategy

### Phase 1: SimulatedOutput Smoke Test
- Create `Forza` instance with `SimulatedOutput`
- Feed a few synthetic `ForzaDataPacket`s through `run()`
- Assert `SimulatedOutput.log` contains expected shift actions

### Phase 2: Recording-Based TCS Tests
- Parse existing recordings at `data2/recordings/`
- Find frames where `tire_combined_slip` exceeds threshold
- Run through `run()` with `SimulatedOutput`
- Assert throttle reduction logged when slip is detected
- Assert throttle restored when slip drops below threshold

### Phase 3: Integration Tests
- Full `run()` with `SimulatedOutput` + all controllers
- Verify arbiter priority: TCS during shift → pass-through
- Verify no double-shifts: shift_pending prevents concurrent shifts
- Verify keyboard quantization: threshold-based press/release transitions

### Test Harness

```python
class TestHarness:
    def __init__(self):
        self.engine = Forza()
        self.output = SimulatedOutput()
        self.engine.set_output_device(self.output)

    def feed_recording(self, path):
        source = PlaybackSource(path)
        while not source.is_finished:
            raw, _ = source.recvfrom(1024)
            fdp = ForzaDataPacket.unpack(raw, 'fh6')
            self.engine.process_packet(fdp)

    def assert_output(self, channel, expected_value, at_index=-1):
        ts, ch, val = self.output.log[at_index]
        assert ch == channel
        assert abs(val - expected_value) < 0.01
```

## Implementation Phases

### Phase 1: Foundation (OutputDevice + ShiftController)
1. `shifting/output_device.py` — Protocol + CommandedState
2. `shifting/keyboard.py` refactor — KeyboardOutput
3. `shifting/simulated_output.py` — Test mock
4. `shifting/shift_controller.py` — Extract shift decision, add shift_pending sync
5. `core/forza.py` — Restructure run() to two-tier dispatch
6. Smoke test with SimulatedOutput

### Phase 2: TCS
7. `control/traction_controller.py` — TCS logic
8. `control/arbiter.py` — Conflict resolution with shift-in-progress handling
9. `core/forza.py` — Add TCS + Arbiter to fast tier
10. Recording-based tests for TCS intervention

### Phase 3: Gamepad + Corner Control
11. `shifting/virtual_gamepad.py` — ViGEmBus GamepadOutput
12. `control/corner_controller.py` — Corner throttle/brake
13. GUI mode switcher + TCS toggle + timing monitor display
14. Integration tests

## Future Work (Out of Scope)

- **Counter-steer (ESC)**: Phase 4. Requires `OutputDevice` to support `set_analog('steer', value)`.
- **Reference Profile System (Phase 2 from roadmap)**: Lap recording + position matching for brake points and speed deltas. Independent of this design.
- **Full-Auto Mode**: Phase 4 from roadmap. Steer + throttle + brake + gear via virtual gamepad.
- **PID controllers**: For brake force modulation in corner control. Current design uses threshold-based control; PID upgrade is additive.
