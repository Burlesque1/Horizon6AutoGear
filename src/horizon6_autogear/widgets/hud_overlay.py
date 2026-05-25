import tkinter

import horizon6_autogear.config.config as constants


def normalize_driving_line(raw_value: int) -> float:
    """Convert raw signed byte (-128..127) to normalized -1.0..1.0.

    Asymmetric: -128/127 ≈ -1.008. The clamp in _update_driving_line handles this.
    """
    return raw_value / 127.0


def brake_indicator_state(raw_diff: int) -> str:
    """Determine brake indicator state from norm_ai_brake_diff.

    Returns 'green' (OK), 'yellow' (approaching), or 'red' (brake now).
    """
    if raw_diff >= constants.COACH_BRAKE_GREEN_THRESHOLD:
        return 'green'
    elif raw_diff >= constants.COACH_BRAKE_YELLOW_THRESHOLD:
        return 'yellow'
    else:
        return 'red'


def tire_grip_state(combined_slip: float) -> str:
    """Determine tire grip state from combined slip value.

    Returns 'green' (good), 'yellow' (approaching limit), or 'red' (at/over limit).
    """
    if combined_slip < constants.COACH_TIRE_SLIP_GREEN:
        return 'green'
    elif combined_slip < constants.COACH_TIRE_SLIP_YELLOW:
        return 'yellow'
    else:
        return 'red'


_STATE_COLORS = {'green': '#00ff88', 'yellow': '#ffdd00', 'red': '#ff4466'}
_DIM_COLOR = '#222244'


class CoachHUD:
    """Floating overlay window for real-time coaching cues.

    Displays three zero-setup indicators:
    - Driving line deviation bar (horizontal, center = on line)
    - Brake timing indicator (3 stacked lights: green/yellow/red)
    - Tire grip dots (4 corners: FL/FR/RL/RR)

    The window is draggable by clicking anywhere on the canvas.
    """

    def __init__(self, parent):
        self.window = tkinter.Toplevel(parent)
        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)
        self.window.configure(bg='#000000')
        try:
            self.window.attributes('-alpha', constants.COACH_HUD_ALPHA)
        except Exception:
            pass

        w, h = constants.COACH_HUD_WIDTH, constants.COACH_HUD_HEIGHT
        screen_w = self.window.winfo_screenwidth()
        x = (screen_w - w) // 2
        self.window.geometry(f"{w}x{h}+{x}+40")

        self.canvas = tkinter.Canvas(self.window, bg='#000000',
                                     highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self._items_created = False
        self.canvas.bind('<Configure>', self._on_configure)

    def _on_configure(self, event):
        if self._items_created:
            return
        w, h = event.width, event.height
        if w < 50 or h < 30:
            return
        self._items_created = True
        c = self.canvas

        # --- Tire grip dots (left side, 2x2) ---
        dot_r = min(6, h * 0.08)
        tx = w * 0.04
        ty_base = h * 0.15
        ty_gap = h * 0.35
        tx_gap = dot_r * 3
        self._tire_dots = {}
        for pos, (px, py) in [
            ('FL', (tx, ty_base)),
            ('FR', (tx + tx_gap, ty_base)),
            ('RL', (tx, ty_base + ty_gap)),
            ('RR', (tx + tx_gap, ty_base + ty_gap)),
        ]:
            self._tire_dots[pos] = c.create_oval(
                px - dot_r, py - dot_r, px + dot_r, py + dot_r,
                fill=_DIM_COLOR, outline='#333355')

        # --- Driving line bar (center) ---
        bar_x1 = w * 0.15
        bar_x2 = w * 0.80
        bar_y = h * 0.55
        bar_h = h * 0.25
        c.create_rectangle(bar_x1, bar_y, bar_x2, bar_y + bar_h,
                           fill='#1a1a2e', outline='#333355')
        cx = (bar_x1 + bar_x2) / 2
        c.create_line(cx, bar_y - 2, cx, bar_y + bar_h + 2,
                      fill='#555577', width=1)
        self._dl_indicator = c.create_rectangle(
            cx - 3, bar_y + 1, cx + 3, bar_y + bar_h - 1,
            fill=_STATE_COLORS['green'], outline='')
        self._dl_geom = {'x1': bar_x1, 'x2': bar_x2, 'y': bar_y,
                         'h': bar_h, 'cx': cx}

        # --- Brake indicator (right side, 3 lights) ---
        light_r = min(7, h * 0.09)
        bx = w * 0.92
        by_base = h * 0.2
        by_gap = light_r * 2.8
        self._brake_active = {}
        for i, state in enumerate(('green', 'yellow', 'red')):
            by = by_base + i * by_gap
            c.create_oval(bx - light_r, by - light_r, bx + light_r, by + light_r,
                          fill=_DIM_COLOR, outline='#333355')
            self._brake_active[state] = c.create_oval(
                bx - light_r + 2, by - light_r + 2,
                bx + light_r - 2, by + light_r - 2,
                fill=_STATE_COLORS[state], outline='', state='hidden')

        # Drag support
        self._drag_offset = (0, 0)
        self.canvas.bind('<Button-1>', self._start_drag)
        self.canvas.bind('<B1-Motion>', self._do_drag)

    def _start_drag(self, event):
        self._drag_offset = (event.x, event.y)

    def _do_drag(self, event):
        x = self.window.winfo_x() + event.x - self._drag_offset[0]
        y = self.window.winfo_y() + event.y - self._drag_offset[1]
        self.window.geometry(f'+{x}+{y}')

    def update(self, driving_line: int, ai_brake_diff: int,
               tire_slips: dict):
        """Update all HUD elements with new telemetry values."""
        if not self._items_created:
            return
        self._update_driving_line(driving_line)
        self._update_brake(ai_brake_diff)
        self._update_tires(tire_slips)

    def _update_driving_line(self, raw):
        norm = normalize_driving_line(raw)
        g = self._dl_geom
        x = g['cx'] + norm * (g['x2'] - g['x1']) / 2
        x = max(g['x1'] + 4, min(x, g['x2'] - 4))
        self.canvas.coords(self._dl_indicator,
                           x - 3, g['y'] + 1, x + 3, g['y'] + g['h'] - 1)
        abs_n = abs(norm)
        if abs_n < constants.COACH_DL_GREEN_THRESHOLD:
            color = _STATE_COLORS['green']
        elif abs_n < constants.COACH_DL_YELLOW_THRESHOLD:
            color = _STATE_COLORS['yellow']
        else:
            color = _STATE_COLORS['red']
        self.canvas.itemconfig(self._dl_indicator, fill=color)

    def _update_brake(self, raw):
        state = brake_indicator_state(raw)
        for s in ('green', 'yellow', 'red'):
            self.canvas.itemconfig(self._brake_active[s],
                                   state='normal' if s == state else 'hidden')

    def _update_tires(self, slips):
        for pos, slip in slips.items():
            if pos in self._tire_dots:
                state = tire_grip_state(slip)
                self.canvas.itemconfig(self._tire_dots[pos],
                                       fill=_STATE_COLORS[state])

    def show(self):
        self.window.deiconify()

    def hide(self):
        self.window.withdraw()

    def destroy(self):
        if self.window.winfo_exists():
            self.window.destroy()
