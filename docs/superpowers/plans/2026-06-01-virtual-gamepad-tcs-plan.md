# Virtual Gamepad + TCS + Corner Control — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add virtual gamepad output (ViGEmBus), traction control (TCS), and corner throttle/brake auto-control to Horizon6AutoGear using a two-tier control architecture.

**Architecture:** Fast tier (TCS, corner control, <5ms, never blocks) + Action tier (gear shifts, threadPool, may block). Controllers are independent and testable via recording playback on macOS using SimulatedOutput.

**Tech Stack:** Python 3, threading.Event + ThreadPoolExecutor, ViGEmBus (Windows-only), pytest

**Design Spec:** `docs/superpowers/specs/2026-06-01-virtual-gamepad-tcs-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `src/horizon6_autogear/shifting/output_device.py` | OutputDevice protocol + CommandedState + SharedState |
| Create | `src/horizon6_autogear/shifting/simulated_output.py` | SimulatedOutput for testing |
| Modify | `src/horizon6_autogear/shifting/keyboard.py` | Add KeyboardOutput class |
| Create | `src/horizon6_autogear/shifting/shift_controller.py` | ShiftController (decision + async execution) |
| Create | `src/horizon6_autogear/control/__init__.py` | Package init |
| Create | `src/horizon6_autogear/control/traction_controller.py` | TCS logic |
| Create | `src/horizon6_autogear/control/arbiter.py` | Output conflict resolution |
| Create | `src/horizon6_autogear/shifting/virtual_gamepad.py` | GamepadOutput (ViGEmBus) |
| Create | `src/horizon6_autogear/control/corner_controller.py` | Corner throttle/brake |
| Modify | `src/horizon6_autogear/core/forza.py` | Restructure run(), integrate controllers |
| Modify | `src/horizon6_autogear/config/config.py` | Add TCS/gamepad constants |
| Create | `tests/test_output_device.py` | Tests for OutputDevice implementations |
| Create | `tests/test_traction_controller.py` | Tests for TCS |
| Create | `tests/test_arbiter.py` | Tests for Arbiter |
| Create | `tests/test_shift_controller.py` | Tests for ShiftController |
| Create | `tests/test_corner_controller.py` | Tests for CornerController |

---

## Phase 1: Foundation (OutputDevice + ShiftController + run() Restructure)

### Task 1: OutputDevice Protocol + CommandedState + SharedState

**Files:**
- Create: `src/horizon6_autogear/shifting/output_device.py`
- Create: `tests/test_output_device.py`

- [ ] **Step 1: Write the failing test**

```python
import sys
import os
import threading
import time

sys.path.append(r'.')
sys.path.append(r'./src')

from horizon6_autogear.shifting.output_device import OutputDevice, CommandedState, SharedState
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_output_device.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Write implementation**

Create `src/horizon6_autogear/shifting/output_device.py`:

```python
from dataclasses import dataclass, field
from threading import Event
from typing import Protocol


@dataclass
class CommandedState:
    throttle: float = 1.0
    brake: float = 0.0


@dataclass
class SharedState:
    shift_pending: Event = field(default_factory=Event)


class OutputDevice(Protocol):
    def set_analog(self, channel: str, value: float) -> None:
        ...

    def execute_shift(self, direction: str) -> None:
        ...
```

Create `src/horizon6_autogear/shifting/simulated_output.py`:

```python
import time


class SimulatedOutput:
    def __init__(self):
        self.log: list[tuple[float, str, float]] = []

    def set_analog(self, channel: str, value: float) -> None:
        self.log.append((time.monotonic(), channel, value))

    def execute_shift(self, direction: str) -> None:
        self.log.append((time.monotonic(), 'shift', direction))

    def clear(self) -> None:
        self.log.clear()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_output_device.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/horizon6_autogear/shifting/output_device.py src/horizon6_autogear/shifting/simulated_output.py tests/test_output_device.py
git commit -m "feat: add OutputDevice protocol, CommandedState, SharedState, SimulatedOutput"
```

---

### Task 2: KeyboardOutput

**Files:**
- Modify: `src/horizon6_autogear/shifting/keyboard.py`
- Modify: `tests/test_output_device.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_output_device.py`:

```python
from unittest.mock import patch, MagicMock


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_output_device.py::test_keyboard_output_press_above_threshold -v`
Expected: FAIL (KeyboardOutput class not found)

- [ ] **Step 3: Write implementation**

Add to end of `src/horizon6_autogear/shifting/keyboard.py`:

```python
class KeyboardOutput:
    """OutputDevice implementation using keyboard simulation.

    Translates float [0.0, 1.0] values to binary press/release based on
    threshold crossing. TCS with keyboard produces on/off cuts, not proportional.
    """
    THROTTLE_THRESHOLD = 0.1

    def __init__(self):
        self._throttle_pressed = False
        self._brake_pressed = False

    def set_analog(self, channel: str, value: float) -> None:
        if channel == 'throttle':
            if value > self.THROTTLE_THRESHOLD and not self._throttle_pressed:
                pressdown_str(constants.ACCELERATION)
                self._throttle_pressed = True
            elif value <= self.THROTTLE_THRESHOLD and self._throttle_pressed:
                release_str(constants.ACCELERATION)
                self._throttle_pressed = False
        elif channel == 'brake':
            if value > self.THROTTLE_THRESHOLD and not self._brake_pressed:
                pressdown_str(constants.BRAKE)
                self._brake_pressed = True
            elif value <= self.THROTTLE_THRESHOLD and self._brake_pressed:
                release_str(constants.BRAKE)
                self._brake_pressed = False

    def execute_shift(self, direction: str) -> None:
        if direction == 'up':
            press_str(constants.UPSHIFT)
        elif direction == 'down':
            press_str(constants.DOWNSHIFT)

    def release_all(self) -> None:
        if self._throttle_pressed:
            release_str(constants.ACCELERATION)
            self._throttle_pressed = False
        if self._brake_pressed:
            release_str(constants.BRAKE)
            self._brake_pressed = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_output_device.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/horizon6_autogear/shifting/keyboard.py tests/test_output_device.py
git commit -m "feat: add KeyboardOutput implementing OutputDevice protocol"
```

---

### Task 3: ShiftController

**Files:**
- Create: `src/horizon6_autogear/shifting/shift_controller.py`
- Create: `tests/test_shift_controller.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_shift_controller.py`:

```python
import sys
import time

sys.path.append(r'.')
sys.path.append(r'./src')

from horizon6_autogear.shifting.output_device import SharedState
from horizon6_autogear.shifting.shift_controller import ShiftController
from horizon6_autogear.shifting.simulated_output import SimulatedOutput


def test_should_shift_up_when_rpm_exceeds_target():
    sc = ShiftController(min_gear=1, max_gear=6, clutch_key='i', upshift_key='e', downshift_key='q')
    sc.shift_point = {1: {'rpmo': 7000, 'speed': 100.0}}
    fdp = _make_fdp(gear=1, rpm=7200, speed=120.0, accel=True, slip_rear=0.2)
    assert sc.should_shift(fdp) == ('up', 1)


def test_should_not_shift_when_no_shift_point():
    sc = ShiftController(min_gear=1, max_gear=6, clutch_key='i', upshift_key='e', downshift_key='q')
    sc.shift_point = {}
    fdp = _make_fdp(gear=1, rpm=7200, speed=120.0, accel=True, slip_rear=0.2)
    assert sc.should_shift(fdp) is None


def test_should_shift_down_when_speed_drops():
    sc = ShiftController(min_gear=1, max_gear=6, clutch_key='i', upshift_key='e', downshift_key='q')
    sc.shift_point = {1: {'rpmo': 7000, 'speed': 100.0}, 2: {'rpmo': 7000, 'speed': 150.0}}
    fdp = _make_fdp(gear=2, rpm=3000, speed=90.0, accel=True, slip_rear=0.2)
    assert sc.should_shift(fdp) == ('down', 2)


def test_should_not_shift_when_slip_too_high():
    sc = ShiftController(min_gear=1, max_gear=6, clutch_key='i', upshift_key='e', downshift_key='q')
    sc.shift_point = {1: {'rpmo': 7000, 'speed': 100.0}}
    fdp = _make_fdp(gear=1, rpm=7200, speed=120.0, accel=True, slip_rear=1.5)
    assert sc.should_shift(fdp) is None


def test_should_not_shift_up_at_max_gear():
    sc = ShiftController(min_gear=1, max_gear=6, clutch_key='i', upshift_key='e', downshift_key='q')
    sc.shift_point = {6: {'rpmo': 7000, 'speed': 200.0}}
    fdp = _make_fdp(gear=6, rpm=7200, speed=220.0, accel=True, slip_rear=0.2)
    assert sc.should_shift(fdp) is None


def _make_fdp(gear, rpm, speed, accel, slip_rear):
    """Create a minimal mock ForzaDataPacket for shift decisions."""
    fdp = type('FDP', (), {})()
    fdp.gear = gear
    fdp.current_engine_rpm = rpm
    fdp.speed = speed / 3.6
    fdp.accel = 255 if accel else 0
    fdp.tire_slip_ratio_RL = slip_rear
    fdp.tire_slip_ratio_RR = slip_rear
    fdp.tire_slip_ratio_FL = 0.0
    fdp.tire_slip_ratio_FR = 0.0
    fdp.tire_slip_angle_RL = 0.0
    fdp.tire_slip_angle_RR = 0.0
    fdp.tire_slip_angle_FL = 0.0
    fdp.tire_slip_angle_FR = 0.0
    fdp.drivetrain_type = 2
    return fdp
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_shift_controller.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Write implementation**

Create `src/horizon6_autogear/shifting/shift_controller.py`:

```python
import time
import logging

import horizon6_autogear.config.config as constants
import horizon6_autogear.shifting.keyboard as keyboard_helper
from horizon6_autogear.shifting.output_device import SharedState


class ShiftController:
    """Determines when to shift and executes shifts asynchronously.

    Extracts shift decision logic from forza.py shifting() into a standalone
    controller. Shift execution is submitted to threadPool with shift_pending
    guard to prevent double-shifts.
    """

    def __init__(self, min_gear: int, max_gear: int,
                 clutch_key: str, upshift_key: str, downshift_key: str,
                 drivetrain: int = 2, clutch_enabled: bool = False,
                 shift_factor: float = 1.0, farming: bool = False,
                 logger: logging.Logger = None):
        self.min_gear = min_gear
        self.max_gear = max_gear
        self.clutch_key = clutch_key
        self.upshift_key = upshift_key
        self.downshift_key = downshift_key
        self.drivetrain = drivetrain
        self.clutch_enabled = clutch_enabled
        self.shift_factor = shift_factor
        self.farming = farming
        self.shift_point = {}
        self.logger = logger or logging.getLogger(__name__)
        self.last_upshift = time.time()
        self.last_downshift = time.time()

    def should_shift(self, fdp) -> tuple[str, int] | None:
        """Decide whether to shift based on telemetry.

        Returns ('up', gear) or ('down', gear) or None.
        """
        gear = fdp.gear
        if not self.shift_point:
            return None
        if fdp.speed <= constants.SPEED_THRESHOLD:
            return None
        if gear < self.min_gear or gear > self.max_gear:
            return None

        slip = (fdp.tire_slip_ratio_RL + fdp.tire_slip_ratio_RR) / 2
        speed = fdp.speed * constants.MS_TO_KMH
        rpm = fdp.current_engine_rpm
        accel = fdp.accel

        if slip >= 1.0:
            return None

        if gear < self.max_gear and accel and gear in self.shift_point:
            target_rpm = self.shift_point[gear]['rpmo'] * self.shift_factor
            target_speed = self.shift_point[gear]['speed'] * self.shift_factor
            if rpm > target_rpm and speed > target_speed:
                return ('up', gear)

        if gear > self.min_gear:
            lower_gear = gear - 1
            if lower_gear not in self.shift_point:
                available = list(self.shift_point.keys())
                if not available:
                    return None
                lower_gear = min(available, key=lambda x: abs(x - (gear - 1)))
            target_down_speed = self.shift_point[lower_gear]['speed'] * self.shift_factor
            if speed < target_down_speed * constants.DOWNSHIFT_SPEED_FACTOR:
                if self.drivetrain == constants.DRIVETRAIN_RWD and gear < constants.RWD_LOW_GEAR_THRESHOLD:
                    return None
                return ('down', gear)

        return None

    def execute_shift(self, direction: str, gear: int, shared_state: SharedState) -> None:
        """Execute a shift in a worker thread. Always clears shift_pending."""
        try:
            if direction == 'up':
                self._do_up_shift(gear)
            elif direction == 'down':
                self._do_down_shift(gear)
        finally:
            shared_state.shift_pending.clear()

    def _do_up_shift(self, gear: int):
        cur = time.time()
        if gear < self.max_gear and cur - self.last_upshift >= constants.UP_SHIFT_COOL_DOWN:
            self.logger.info(f'[ShiftController] up shift: {gear} -> {gear + 1}')
            if self.clutch_enabled:
                keyboard_helper.pressdown_str(self.clutch_key)
            time.sleep(constants.DELAY_CLUTCH_TO_SHIFT)
            keyboard_helper.press_str(self.upshift_key)
            time.sleep(constants.DELAY_SHIFT_TO_CLUTCH)
            if self.clutch_enabled:
                keyboard_helper.release_str(self.clutch_key)
            self.last_upshift = cur

    def _do_down_shift(self, gear: int):
        cur = time.time()
        if gear > self.min_gear and cur - self.last_downshift >= constants.DOWN_SHIFT_COOL_DOWN:
            self.logger.info(f'[ShiftController] down shift: {gear} -> {gear - 1}')
            if self.clutch_enabled:
                keyboard_helper.pressdown_str(self.clutch_key)
                if not self.farming:
                    keyboard_helper.pressdown_str(constants.ACCELERATION)
                    time.sleep(constants.BLIP_THROTTLE_DURATION)
                    keyboard_helper.release_str(constants.ACCELERATION)
            time.sleep(constants.DELAY_CLUTCH_TO_SHIFT)
            keyboard_helper.press_str(self.downshift_key)
            time.sleep(constants.DELAY_SHIFT_TO_CLUTCH)
            if self.clutch_enabled:
                keyboard_helper.release_str(self.clutch_key)
            self.last_downshift = cur
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_shift_controller.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/horizon6_autogear/shifting/shift_controller.py tests/test_shift_controller.py
git commit -m "feat: add ShiftController with async shift execution"
```

---

### Task 4: Restructure forza.py run() Loop

**Files:**
- Modify: `src/horizon6_autogear/core/forza.py`

This is the most invasive change. The `shifting()` method is replaced by ShiftController + controller dispatch in `run()`.

- [ ] **Step 1: Add imports at top of forza.py**

Add after existing imports at line 23:

```python
from horizon6_autogear.shifting.output_device import SharedState
from horizon6_autogear.shifting.shift_controller import ShiftController
from horizon6_autogear.shifting.keyboard import KeyboardOutput
```

- [ ] **Step 2: Add SharedState and ShiftController to __init__**

Add after `self.recorder = None` (line 89) in `__init__`:

```python
        self.shared_state = SharedState()
        self.output_device = KeyboardOutput()
        self.shift_controller = None
```

- [ ] **Step 3: Replace run() method**

Replace the `run()` method (lines 431-481) with:

```python
    def run(self, update_tree_func=lambda *args: None, update_car_gui_func=lambda *args: None, display_only=False):
        """run the auto shifting

        Args:
            update_tree_func (, optional): update tree view callback. Defaults to None.
            update_car_gui_func (, optional): update car gui callback. Defaults to None.
            display_only (bool): if True, receive telemetry without shifting or key presses.
        """
        try:
            self.logger.debug('[Run] started' + (' (display only)' if display_only else ''))
            helper.create_socket(self)
            iteration = -1
            self.reset_car = 0
            self.reset_time = time.time()
            refresh_time = time.time()
            first_load = True

            if not display_only and self.farming:
                keyboard_helper.pressdown_str(constants.ACCELERATION)

            while self.isRunning:
                fdp = helper.nextFdp(self.server_socket, self.packet_format, self.recorder)

                if fdp is None or fdp.car_ordinal <= 0:
                    continue

                if update_car_gui_func is not None and time.time() - refresh_time > constants.GUI_REFRESH_INTERVAL:
                    self.threadPool.submit(update_car_gui_func, fdp)
                    refresh_time = time.time()

                self.__update_forza_info(fdp, update_tree_func, first_load=first_load)
                first_load = False

                if not display_only:
                    self.__exp_farming_setup(fdp)

                    if not self.shared_state.shift_pending.is_set():
                        iteration = self._dispatch_controllers(iteration, fdp)

        except Exception as e:
            self.logger.exception(e)
        finally:
            self.isRunning = False
            if not display_only and self.farming:
                keyboard_helper.release_str(constants.ACCELERATION)

            helper.close_socket(self)
            self.logger.debug('[Run] finished')

    def _init_shift_controller(self):
        """Initialize shift controller with current car config."""
        self.shift_controller = ShiftController(
            min_gear=self.minGear,
            max_gear=self.maxGear,
            clutch_key=self.clutch,
            upshift_key=self.upshift,
            downshift_key=self.downshift,
            drivetrain=self.car_drivetrain,
            clutch_enabled=self.enable_clutch,
            shift_factor=self.shift_point_factor,
            farming=self.farming,
            logger=self.logger,
        )
        self.shift_controller.shift_point = self.shift_point

    def _dispatch_controllers(self, iteration, fdp):
        """Fast tier: shift decision + dispatch. Called when shift_pending is clear."""
        iteration = iteration + 1

        if self.logger.isEnabledFor(logging.DEBUG):
            debug_log = fdp.to_list(debug_properties)
            self.logger.debug(f'[{iteration}] {debug_log}')

        if not self.shift_point or fdp.speed <= constants.SPEED_THRESHOLD:
            return iteration

        gear = fdp.gear
        if gear < self.minGear or gear > self.maxGear:
            return iteration

        if self.shift_controller is None or self.shift_controller.shift_point != self.shift_point:
            self._init_shift_controller()

        decision = self.shift_controller.should_shift(fdp)
        if decision is not None:
            direction, gear_num = decision
            if not self.shared_state.shift_pending.is_set():
                self.shared_state.shift_pending.set()
                self.threadPool.submit(
                    self.shift_controller.execute_shift,
                    direction, gear_num, self.shared_state
                )

        return iteration
```

- [ ] **Step 4: Keep shifting() for backward compatibility but mark deprecated**

Do NOT delete `shifting()` yet — it's still referenced by existing code patterns. Add a deprecation comment at line 298:

```python
    def shifting(self, iteration, fdp):
        """shifting func (deprecated: use _dispatch_controllers via run())
```

The method body stays unchanged for now. It will be removed once GUI integration is complete.

- [ ] **Step 5: Run existing tests to verify no regression**

Run: `pytest tests/test_forza.py -v`
Expected: PASS (test_analysis still works — it doesn't use run())

- [ ] **Step 6: Commit**

```bash
git add src/horizon6_autogear/core/forza.py
git commit -m "feat: restructure run() loop with ShiftController and shared state"
```

---

## Phase 2: TCS + Arbiter

### Task 5: TractionController

**Files:**
- Create: `src/horizon6_autogear/control/__init__.py`
- Create: `src/horizon6_autogear/control/traction_controller.py`
- Create: `tests/test_traction_controller.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_traction_controller.py`:

```python
import sys

sys.path.append(r'.')
sys.path.append(r'./src')

from horizon6_autogear.control.traction_controller import TractionController


def test_no_intervention_below_min_speed():
    tc = TractionController()
    fdp = _make_fdp(speed=3.0, combined_slip_rl=0.8, combined_slip_rr=0.9, drivetrain=1)
    assert tc.compute(fdp) == 1.0


def test_no_intervention_below_slip_threshold():
    tc = TractionController()
    fdp = _make_fdp(speed=30.0, combined_slip_rl=0.2, combined_slip_rr=0.3, drivetrain=1)
    assert tc.compute(fdp) == 1.0


def test_rwd_intervention_on_rear_slip():
    tc = TractionController()
    fdp = _make_fdp(speed=30.0, combined_slip_rl=0.7, combined_slip_rr=0.8, drivetrain=1)
    assert tc.compute(fdp) < 1.0


def test_fwd_intervention_on_front_slip():
    tc = TractionController()
    fdp = _make_fdp(speed=30.0, combined_slip_fl=0.7, combined_slip_fr=0.8, drivetrain=0)
    assert tc.compute(fdp) < 1.0


def test_fwd_ignores_rear_slip():
    tc = TractionController()
    fdp = _make_fdp(speed=30.0, combined_slip_rl=0.9, combined_slip_rr=0.9, drivetrain=0)
    assert tc.compute(fdp) == 1.0


def test_awd_monitors_all_wheels():
    tc = TractionController()
    fdp = _make_fdp(speed=30.0, combined_slip_rl=0.1, combined_slip_rr=0.1,
                    combined_slip_fl=0.1, combined_slip_fr=0.8, drivetrain=2)
    assert tc.compute(fdp) < 1.0


def test_custom_threshold():
    tc = TractionController(slip_threshold=0.3, throttle_reduction=0.4)
    fdp = _make_fdp(speed=30.0, combined_slip_rl=0.4, combined_slip_rr=0.5, drivetrain=1)
    assert tc.compute(fdp) == 0.4


def _make_fdp(speed, combined_slip_rl=0.0, combined_slip_rr=0.0,
              combined_slip_fl=0.0, combined_slip_fr=0.0, drivetrain=1):
    fdp = type('FDP', (), {})()
    fdp.speed = speed
    fdp.tire_combined_slip_RL = combined_slip_rl
    fdp.tire_combined_slip_RR = combined_slip_rr
    fdp.tire_combined_slip_FL = combined_slip_fl
    fdp.tire_combined_slip_FR = combined_slip_fr
    fdp.drivetrain_type = drivetrain
    return fdp
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_traction_controller.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Write implementation**

Create `src/horizon6_autogear/control/__init__.py`:

```python
```

Create `src/horizon6_autogear/control/traction_controller.py`:

```python
class TractionController:
    """TCS: Detects wheel slip and reduces throttle output.

    Monitors combined_slip on drive wheels based on drivetrain type.
    Returns 1.0 (no intervention) or a reduced throttle value.
    """

    def __init__(self, slip_threshold: float = 0.5,
                 min_speed: float = 5.0,
                 throttle_reduction: float = 0.3):
        self.slip_threshold = slip_threshold
        self.min_speed = min_speed
        self.throttle_reduction = throttle_reduction

    def compute(self, fdp) -> float:
        """Returns target throttle (0.0-1.0). 1.0 = no intervention."""
        if fdp.speed < self.min_speed:
            return 1.0

        if fdp.drivetrain_type == 1:    # RWD
            drive_slip = max(fdp.tire_combined_slip_RL, fdp.tire_combined_slip_RR)
        elif fdp.drivetrain_type == 0:  # FWD
            drive_slip = max(fdp.tire_combined_slip_FL, fdp.tire_combined_slip_FR)
        else:                            # AWD
            drive_slip = max(fdp.tire_combined_slip_FL, fdp.tire_combined_slip_FR,
                             fdp.tire_combined_slip_RL, fdp.tire_combined_slip_RR)

        if drive_slip > self.slip_threshold:
            return self.throttle_reduction
        return 1.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_traction_controller.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/horizon6_autogear/control/__init__.py src/horizon6_autogear/control/traction_controller.py tests/test_traction_controller.py
git commit -m "feat: add TractionController (TCS) with per-drivetrain slip detection"
```

---

### Task 6: Arbiter

**Files:**
- Create: `src/horizon6_autogear/control/arbiter.py`
- Create: `tests/test_arbiter.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_arbiter.py`:

```python
import sys

sys.path.append(r'.')
sys.path.append(r'./src')

from horizon6_autogear.control.arbiter import Arbiter


def test_no_intervention_passes_driver_throttle():
    arb = Arbiter()
    result = arb.resolve(driver_throttle=0.8, tcs_throttle=1.0,
                         corner_throttle=1.0, corner_brake=0.0,
                         shift_pending=False)
    assert result.throttle == 0.8
    assert result.brake == 0.0


def test_tcs_reduces_throttle():
    arb = Arbiter()
    result = arb.resolve(driver_throttle=1.0, tcs_throttle=0.3,
                         corner_throttle=1.0, corner_brake=0.0,
                         shift_pending=False)
    assert result.throttle == 0.3


def test_corner_and_tcs_both_reduce():
    arb = Arbiter()
    result = arb.resolve(driver_throttle=1.0, tcs_throttle=0.5,
                         corner_throttle=0.7, corner_brake=0.0,
                         shift_pending=False)
    assert result.throttle == 0.5


def test_corner_brake_passes_through():
    arb = Arbiter()
    result = arb.resolve(driver_throttle=0.5, tcs_throttle=1.0,
                         corner_throttle=1.0, corner_brake=0.4,
                         shift_pending=False)
    assert result.brake == 0.4


def test_shift_pending_suppresses_tcs():
    arb = Arbiter()
    result = arb.resolve(driver_throttle=0.8, tcs_throttle=0.3,
                         corner_throttle=0.7, corner_brake=0.4,
                         shift_pending=True)
    assert result.throttle == 0.8
    assert result.brake == 0.0


def test_defaults_when_controllers_missing():
    arb = Arbiter()
    result = arb.resolve(driver_throttle=0.9, tcs_throttle=1.0,
                         corner_throttle=1.0, corner_brake=0.0,
                         shift_pending=False)
    assert result.throttle == 0.9
    assert result.brake == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_arbiter.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Write implementation**

Create `src/horizon6_autogear/control/arbiter.py`:

```python
from horizon6_autogear.shifting.output_device import CommandedState


class Arbiter:
    """Resolves throttle/brake conflicts between controllers.

    Safety-first: lowest-wins for throttle. During shift, TCS and corner
    control are suppressed — drivetrain is disconnected via clutch.
    """

    def resolve(self, driver_throttle: float, tcs_throttle: float,
                corner_throttle: float, corner_brake: float,
                shift_pending: bool) -> CommandedState:
        if shift_pending:
            return CommandedState(throttle=driver_throttle, brake=0.0)

        return CommandedState(
            throttle=min(driver_throttle, tcs_throttle, corner_throttle),
            brake=corner_brake,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_arbiter.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/horizon6_autogear/control/arbiter.py tests/test_arbiter.py
git commit -m "feat: add Arbiter for output conflict resolution"
```

---

### Task 7: Integrate TCS + Arbiter into run()

**Files:**
- Modify: `src/horizon6_autogear/core/forza.py`
- Modify: `src/horizon6_autogear/config/config.py`

- [ ] **Step 1: Add config constants**

Add to `src/horizon6_autogear/config/config.py` after the shifting thresholds section (after line 124):

```python
TCS_SLIP_THRESHOLD = 0.5
TCS_MIN_SPEED = 5.0
TCS_THROTTLE_REDUCTION = 0.3
TCS_ENABLED = True
```

- [ ] **Step 2: Add imports in forza.py**

Add to imports:

```python
from horizon6_autogear.control.traction_controller import TractionController
from horizon6_autogear.control.arbiter import Arbiter
```

- [ ] **Step 3: Add TCS and Arbiter to __init__**

Add after `self.shift_controller = None`:

```python
        self.tcs_enabled = constants.TCS_ENABLED
        self.traction_controller = TractionController(
            slip_threshold=constants.TCS_SLIP_THRESHOLD,
            min_speed=constants.TCS_MIN_SPEED,
            throttle_reduction=constants.TCS_THROTTLE_REDUCTION,
        )
        self.arbiter = Arbiter()
```

- [ ] **Step 4: Update _dispatch_controllers to include TCS + Arbiter**

Replace the `_dispatch_controllers` method with:

```python
    def _dispatch_controllers(self, iteration, fdp):
        """Fast tier: TCS + shift decision + arbiter dispatch."""
        iteration = iteration + 1

        if self.logger.isEnabledFor(logging.DEBUG):
            debug_log = fdp.to_list(debug_properties)
            self.logger.debug(f'[{iteration}] {debug_log}')

        if not self.shift_point or fdp.speed <= constants.SPEED_THRESHOLD:
            return iteration

        gear = fdp.gear
        if gear < self.minGear or gear > self.maxGear:
            return iteration

        if self.shift_controller is None or self.shift_controller.shift_point != self.shift_point:
            self._init_shift_controller()

        tcs_throttle = 1.0
        if self.tcs_enabled:
            tcs_throttle = self.traction_controller.compute(fdp)

        driver_throttle = fdp.accel / 255.0

        commanded = self.arbiter.resolve(
            driver_throttle=driver_throttle,
            tcs_throttle=tcs_throttle,
            corner_throttle=1.0,
            corner_brake=0.0,
            shift_pending=self.shared_state.shift_pending.is_set(),
        )

        self.output_device.set_analog('throttle', commanded.throttle)
        self.output_device.set_analog('brake', commanded.brake)

        decision = self.shift_controller.should_shift(fdp)
        if decision is not None:
            direction, gear_num = decision
            if not self.shared_state.shift_pending.is_set():
                self.shared_state.shift_pending.set()
                self.threadPool.submit(
                    self.shift_controller.execute_shift,
                    direction, gear_num, self.shared_state
                )

        return iteration
```

- [ ] **Step 5: Run all tests**

Run: `pytest tests/ -v`
Expected: All PASS (existing test_forza.py + new tests)

- [ ] **Step 6: Commit**

```bash
git add src/horizon6_autogear/core/forza.py src/horizon6_autogear/config/config.py
git commit -m "feat: integrate TCS + Arbiter into run() loop"
```

---

## Phase 3: Gamepad + Corner Control + GUI

### Task 8: GamepadOutput (ViGEmBus)

**Files:**
- Create: `src/horizon6_autogear/shifting/virtual_gamepad.py`

- [ ] **Step 1: Write implementation**

Create `src/horizon6_autogear/shifting/virtual_gamepad.py`:

```python
import sys

if sys.platform == 'win32':
    try:
        import vigem_client
    except ImportError:
        vigem_client = None
else:
    vigem_client = None


class GamepadOutput:
    """OutputDevice implementation using ViGEmBus virtual Xbox controller.

    Provides analog throttle/brake output (0.0-1.0). Windows-only.
    Falls back gracefully if ViGEmBus driver or Python binding is missing.
    """

    def __init__(self):
        if vigem_client is None:
            raise RuntimeError(
                "GamepadOutput requires Windows with ViGEmBus installed. "
                "Install vigem-client: pip install vigem-client"
            )
        self._client = vigem_client.ViGEmBusClient()
        self._controller = self._client.create_x360_controller()
        self._controller.connect()
        self._throttle_value = 0.0
        self._brake_value = 0.0

    def set_analog(self, channel: str, value: float) -> None:
        value = max(0.0, min(1.0, value))
        if channel == 'throttle':
            if value != self._throttle_value:
                self._controller.set_axis_value(
                    vigem_client.X360_AXIS.RT, int(value * 255)
                )
                self._throttle_value = value
        elif channel == 'brake':
            if value != self._brake_value:
                self._controller.set_axis_value(
                    vigem_client.X360_AXIS.LT, int(value * 255)
                )
                self._brake_value = value

    def execute_shift(self, direction: str) -> None:
        if direction == 'up':
            self._controller.press_button(vigem_client.X360_BUTTON.B)
            import time
            time.sleep(0.05)
            self._controller.release_button(vigem_client.X360_BUTTON.B)
        elif direction == 'down':
            self._controller.press_button(vigem_client.X360_BUTTON.A)
            import time
            time.sleep(0.05)
            self._controller.release_button(vigem_client.X360_BUTTON.A)

    def release_all(self) -> None:
        self.set_analog('throttle', 0.0)
        self.set_analog('brake', 0.0)

    @staticmethod
    def is_available() -> bool:
        return vigem_client is not None
```

- [ ] **Step 2: Commit**

```bash
git add src/horizon6_autogear/shifting/virtual_gamepad.py
git commit -m "feat: add GamepadOutput with ViGEmBus virtual Xbox controller"
```

---

### Task 9: CornerController

**Files:**
- Create: `src/horizon6_autogear/control/corner_controller.py`
- Create: `tests/test_corner_controller.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_corner_controller.py`:

```python
import sys

sys.path.append(r'.')
sys.path.append(r'./src')

from horizon6_autogear.control.corner_controller import CornerController


def test_no_intervention_on_straight():
    cc = CornerController()
    fdp = _make_fdp(steer=0.1, max_slip=0.2)
    throttle, brake = cc.compute(fdp)
    assert throttle == 1.0
    assert brake == 0.0


def test_reduce_throttle_in_corner_with_slip():
    cc = CornerController()
    fdp = _make_fdp(steer=0.5, max_slip=0.5)
    throttle, brake = cc.compute(fdp)
    assert throttle < 1.0
    assert brake == 0.0


def test_corner_without_slip_no_intervention():
    cc = CornerController()
    fdp = _make_fdp(steer=0.5, max_slip=0.2)
    throttle, brake = cc.compute(fdp)
    assert throttle == 1.0
    assert brake == 0.0


def test_custom_thresholds():
    cc = CornerController(steer_threshold=0.5, slip_limit=0.3, throttle_reduction=0.5)
    fdp = _make_fdp(steer=0.6, max_slip=0.4)
    throttle, brake = cc.compute(fdp)
    assert throttle == 0.5


def _make_fdp(steer, max_slip):
    fdp = type('FDP', (), {})()
    fdp.steer = steer
    fdp.speed = 30.0
    fdp.tire_combined_slip_FL = max_slip
    fdp.tire_combined_slip_FR = max_slip * 0.9
    fdp.tire_combined_slip_RL = max_slip * 0.8
    fdp.tire_combined_slip_RR = max_slip * 0.7
    return fdp
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_corner_controller.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Write implementation**

Create `src/horizon6_autogear/control/corner_controller.py`:

```python
class CornerController:
    """Corner throttle/brake auto-control.

    Reduces throttle when steering input exceeds threshold AND tire slip
    indicates the car is at or beyond grip limit in a corner.
    """

    def __init__(self, steer_threshold: float = 0.3,
                 slip_limit: float = 0.4,
                 throttle_reduction: float = 0.7):
        self.steer_threshold = steer_threshold
        self.slip_limit = slip_limit
        self.throttle_reduction = throttle_reduction

    def compute(self, fdp) -> tuple[float, float]:
        """Returns (corner_throttle, corner_brake)."""
        if abs(fdp.steer) < self.steer_threshold:
            return 1.0, 0.0

        max_slip = max(fdp.tire_combined_slip_FL, fdp.tire_combined_slip_FR,
                       fdp.tire_combined_slip_RL, fdp.tire_combined_slip_RR)

        if max_slip > self.slip_limit:
            return self.throttle_reduction, 0.0

        return 1.0, 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_corner_controller.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/horizon6_autogear/control/corner_controller.py tests/test_corner_controller.py
git commit -m "feat: add CornerController for corner throttle/brake control"
```

---

### Task 10: Integrate CornerController + Gamepad into run()

**Files:**
- Modify: `src/horizon6_autogear/core/forza.py`

- [ ] **Step 1: Add imports**

```python
from horizon6_autogear.control.corner_controller import CornerController
```

- [ ] **Step 2: Add CornerController to __init__**

Add after `self.arbiter = Arbiter()`:

```python
        self.corner_controller = CornerController()
```

- [ ] **Step 3: Update _dispatch_controllers to include CornerController**

Replace the arbiter call in `_dispatch_controllers`:

```python
        corner_throttle, corner_brake = self.corner_controller.compute(fdp)

        commanded = self.arbiter.resolve(
            driver_throttle=driver_throttle,
            tcs_throttle=tcs_throttle,
            corner_throttle=corner_throttle,
            corner_brake=corner_brake,
            shift_pending=self.shared_state.shift_pending.is_set(),
        )
```

- [ ] **Step 4: Add output device selection method**

```python
    def set_output_device(self, device):
        """Swap output device at runtime (atomic reference swap)."""
        old = self.output_device
        if hasattr(old, 'release_all'):
            old.release_all()
        self.output_device = device
        self.logger.info(f'[Output] switched to {type(device).__name__}')
```

- [ ] **Step 5: Run all tests**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/horizon6_autogear/core/forza.py
git commit -m "feat: integrate CornerController and output device switching"
```

---

### Task 11: GUI Integration

**Files:**
- Modify: `src/horizon6_autogear/gui.py`

This task adds TCS toggle and output device selector to the web GUI. The exact implementation depends on the current web theme structure.

- [ ] **Step 1: Add API methods to Api class in gui.py**

Add toggle methods following the existing pattern (e.g., `toggle_clutch`, `toggle_farm`):

```python
    def toggle_tcs(self):
        self.engine.tcs_enabled = not self.engine.tcs_enabled
        return self.engine.tcs_enabled

    def get_tcs_state(self):
        return self.engine.tcs_enabled

    def set_output_mode(self, mode):
        from horizon6_autogear.shifting.simulated_output import SimulatedOutput
        from horizon6_autogear.shifting.virtual_gamepad import GamepadOutput

        if mode == 'keyboard':
            self.engine.set_output_device(KeyboardOutput())
        elif mode == 'gamepad':
            try:
                self.engine.set_output_device(GamepadOutput())
            except RuntimeError as e:
                return {'error': str(e)}
        elif mode == 'simulated':
            self.engine.set_output_device(SimulatedOutput())
        return {'mode': mode}
```

- [ ] **Step 2: Add i18n strings to config.py**

```python
TCS_LABEL = ['TCS', '牵引力控制']
```

- [ ] **Step 3: Wire buttons in web theme JS**

In the theme's `api.js`, wire the new buttons following the existing `wireBtn` / `wireSettings` pattern.

- [ ] **Step 4: Commit**

```bash
git add src/horizon6_autogear/gui.py src/horizon6_autogear/config/config.py
git commit -m "feat: add TCS toggle and output mode selector to GUI"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] OutputDevice protocol + 3 implementations → Tasks 1, 2, 8
- [x] ShiftController with shift_pending → Task 3
- [x] run() restructure → Task 4
- [x] TractionController → Task 5
- [x] Arbiter → Task 6
- [x] TCS + Arbiter integration → Task 7
- [x] CornerController → Task 9
- [x] Corner + Gamepad integration → Task 10
- [x] GUI → Task 11

**Placeholder scan:** No TBD/TODO found.

**Type consistency:** `should_shift()` returns `tuple[str, int] | None` — matches usage in Tasks 4, 7, 10. `set_analog(channel, value)` — same signature across KeyboardOutput, GamepadOutput, SimulatedOutput.
