"""
macOS keyboard listener using Quartz CGEventTap.

Replaces pynput.keyboard.Listener on macOS to avoid SIGTRAP crashes
caused by pynput's background thread calling TSMGetInputSourceProperty
from a non-main thread.

Interface matches pynput.Listener for easy swap:
- macOSKeyboardListener(on_press)
- .start()
- .stop()
- .is_alive
- .join()

Only handles the 6 keys used by the application:
F7, F8, F10, Pause, End, Escape
"""

import threading
import time
from typing import Optional, Callable, Any

# macOS-specific imports
try:
    from Quartz import (
        CGEventTapCreate, kCGSessionEventTap, kCGHeadInsertEventTap,
        kCGEventKeyDown, kCGEventTapOptionDefault,
        CFMachPortInvalidate,
        kCFRunLoopCommonModes,
        CGEventGetIntegerValueField, kCGKeyboardEventKeycode,
        CGEventTapEnable,
        CGEventMaskBit
    )
    from CoreFoundation import (
        CFMachPortCreateRunLoopSource, CFRunLoopAddSource,
        CFRunLoopGetCurrent,
        kCFRunLoopDefaultMode, CFRunLoopRunInMode
    )
    HAS_QUARTZ = True
except ImportError:
    HAS_QUARTZ = False

# We'll import pynput.Key directly for key constants
# Note: We import this lazily in _handle_key_event to avoid
# unnecessary pynput import on non-macOS platforms

# Quartz virtual keycodes for macOS
# From /System/Library/Frameworks/Carbon.framework/Frameworks/HIToolbox.framework/Headers/Events.h
kVK_F1 = 0x7A
kVK_F2 = 0x78
kVK_F3 = 0x63
kVK_F4 = 0x76
kVK_F5 = 0x60
kVK_F6 = 0x61
kVK_F7 = 0x62
kVK_F8 = 0x64
kVK_F9 = 0x65
kVK_F10 = 0x6D
kVK_F11 = 0x67
kVK_F12 = 0x6F
kVK_Escape = 0x35
kVK_Return = 0x24
kVK_Tab = 0x30
kVK_Space = 0x31
kVK_Delete = 0x33
kVK_ForwardDelete = 0x75
kVK_Home = 0x73
kVK_End = 0x77
kVK_PageUp = 0x74
kVK_PageDown = 0x79
kVK_LeftArrow = 0x7B
kVK_RightArrow = 0x7C
kVK_DownArrow = 0x7D
kVK_UpArrow = 0x7E
kVK_Pause = 0x71  # Actually Break key, closest to Pause

# Map Quartz keycodes to pynput Key objects
# We'll create this mapping lazily when needed
QUARTZ_TO_PYNPUT_KEYS = {
    kVK_F7: 'f7',
    kVK_F8: 'f8',
    kVK_F9: 'f9',
    kVK_F10: 'f10',
    kVK_F12: 'f12',
    kVK_Pause: 'pause',
    kVK_End: 'end',
    kVK_Escape: 'esc',
}

class macOSKeyboardListener:
    """macOS keyboard listener using CGEventTap."""

    def __init__(self, on_press: Callable[[Any], None]):
        """
        Initialize the listener.

        Args:
            on_press: Callback function that receives key events.
                     Should accept a single argument (the key).
        """
        if not HAS_QUARTZ:
            raise RuntimeError("macOSKeyboardListener requires macOS with Quartz framework")

        self._on_press = on_press
        self._tap = None
        self._run_loop_source = None
        self._run_loop_thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.is_alive = False

    def _tap_callback(self, proxy: Any, event_type: int, event: Any, refcon: Any) -> Any:
        """
        Callback for CGEventTap.

        Returns the event unchanged (pass-through) so keyboard works normally.
        """
        try:
            if event_type == kCGEventKeyDown:
                keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
                self._handle_key_event(keycode)
        except Exception:
            # Don't let exceptions in our callback break the event tap
            pass

        return event  # Pass through, don't consume

    def _handle_key_event(self, quartz_keycode: int):
        """Convert Quartz keycode and call on_press callback."""
        if quartz_keycode in QUARTZ_TO_PYNPUT_KEYS:
            try:
                # Lazy import pynput to avoid unnecessary dependency
                from pynput.keyboard import Key

                # Get the key name from our mapping
                key_name = QUARTZ_TO_PYNPUT_KEYS[quartz_keycode]

                # Convert to pynput Key object
                # Key class has attributes like Key.f7, Key.f8, etc.
                # We can use getattr to get the appropriate Key attribute
                pynput_key = getattr(Key, key_name, None)

                if pynput_key is not None:
                    self._on_press(pynput_key)
            except Exception:
                # Don't let exceptions break the listener
                pass

    def start(self):
        """Start the keyboard listener."""
        with self._lock:
            if self.is_alive:
                return

            # Create event tap for key down events
            event_mask = CGEventMaskBit(kCGEventKeyDown)

            # Create the event tap
            self._tap = CGEventTapCreate(
                kCGSessionEventTap,  # Tap session-level events
                kCGHeadInsertEventTap,  # Insert at head of event list
                kCGEventTapOptionDefault,  # Default options
                event_mask,
                self._tap_callback,
                None  # No refcon needed
            )

            if self._tap is None:
                raise RuntimeError("Failed to create CGEventTap. "
                                 "Make sure Accessibility permission is granted in System Settings.")

            # Create run loop source from the tap
            self._run_loop_source = CFMachPortCreateRunLoopSource(
                None, self._tap, 0
            )

            # Start run loop in background thread
            self._stop_event.clear()
            self._run_loop_thread = threading.Thread(
                target=self._run_loop_worker,
                daemon=True,
                name="CGEventTap-RunLoop"
            )
            self._run_loop_thread.start()

            # Wait a bit for run loop to start
            time.sleep(0.1)
            self.is_alive = True

    def _run_loop_worker(self):
        """Worker thread that runs the CFRunLoop."""
        # Get current run loop
        run_loop = CFRunLoopGetCurrent()

        # Add the source to the run loop
        CFRunLoopAddSource(
            run_loop,
            self._run_loop_source,
            kCFRunLoopCommonModes
        )

        # Enable the event tap
        CGEventTapEnable(self._tap, True)

        # Run the run loop until stopped
        while not self._stop_event.is_set():
            CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0.1, False)

        # Clean up
        if self._tap:
            CGEventTapEnable(self._tap, False)
            CFMachPortInvalidate(self._tap)

    def stop(self):
        """Stop the keyboard listener."""
        with self._lock:
            if not self.is_alive:
                return

            self._stop_event.set()

            if self._run_loop_thread and self._run_loop_thread.is_alive():
                self._run_loop_thread.join(timeout=1.0)

            self._run_loop_thread = None
            self._run_loop_source = None
            self._tap = None
            self.is_alive = False

    def join(self, timeout: Optional[float] = None):
        """
        Wait for the listener thread to terminate.

        Args:
            timeout: Maximum time to wait in seconds.
        """
        if self._run_loop_thread:
            self._run_loop_thread.join(timeout=timeout)