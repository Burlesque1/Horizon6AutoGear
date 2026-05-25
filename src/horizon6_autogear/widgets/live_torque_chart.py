"""Real-time torque curve chart using Tkinter Canvas pre-build pattern."""

import tkinter

from horizon6_autogear.config.config import DEFAULT_MAX_GEAR

# === Chart Colors (glass theme) ===
CHART_BG = '#0d0d1a'
CHART_GRID = '#2a2a4e'
CHART_TEXT = '#8888bb'
CHART_TITLE = '#00d4ff'
CHART_AXIS = '#e0e0ff'
SHIFT_COLOR = '#ff4466'
CURSOR_COLOR = '#ffffff'
ACTIVE_GLOW = '#667eea'

# Gear colors (up to 10 gears)
GEAR_COLORS = [
    '#ff4466', '#ff9500', '#ffdd00', '#00ff88', '#00d4ff',
    '#667eea', '#764ba2', '#c44dff', '#ff6b9d', '#45b7d1',
]

# Chart margins (pixels)
MARGIN_LEFT = 55
MARGIN_RIGHT = 60
MARGIN_TOP = 25
MARGIN_BOTTOM = 35

# Grid divisions
GRID_DIVISIONS = 5
DOT_RADIUS = 4

PLACEHOLDER_TEXT = ['Run Analysis to see torque curves', '运行分析以查看扭矩曲线']


class LiveTorqueChart:
    """Self-contained Canvas torque chart with static curves and live cursor.

    Canvas items are created once in _on_configure and updated via coords()/itemconfig().
    """

    def __init__(self, canvas: tkinter.Canvas, lang_index: int = 0):
        self.canvas = canvas
        self._items_created = False
        self._analysis_loaded = False
        self._active_gear = -1
        self._lang_index = lang_index

        # Data ranges
        self._x_min = 0
        self._x_max = 9000
        self._y_min = 0
        self._y_max = 1000

        # Plot area bounds (set in _on_configure)
        self._plot_left = 0
        self._plot_top = 0
        self._plot_right = 0
        self._plot_bottom = 0

        # Canvas item IDs
        self._grid_lines = []
        self._axis_labels = []
        self._x_title = None
        self._y_title = None
        self._chart_title = None
        self._gear_lines = {}
        self._gear_legends = {}
        self._shift_lines = {}
        self._cursor_dot = None
        self._cursor_vline = None
        self._cursor_readout = None
        self._placeholder = None

        # Deferred analysis data (if configure hasn't fired yet)
        self._pending_forza = None

        self.canvas.bind('<Configure>', self._on_configure)

    def _on_configure(self, event):
        if self._items_created:
            return
        self._items_created = True

        w, h = event.width, event.height
        self._plot_left = MARGIN_LEFT
        self._plot_top = MARGIN_TOP
        self._plot_right = w - MARGIN_RIGHT
        self._plot_bottom = h - MARGIN_BOTTOM

        self.canvas.configure(bg=CHART_BG)

        # Grid lines
        plot_w = self._plot_right - self._plot_left
        plot_h = self._plot_bottom - self._plot_top
        for i in range(GRID_DIVISIONS + 1):
            frac = i / GRID_DIVISIONS
            y = self._plot_top + frac * plot_h
            self._grid_lines.append(self.canvas.create_line(
                self._plot_left, y, self._plot_right, y,
                fill=CHART_GRID, dash=(2, 4)))
            x = self._plot_left + frac * plot_w
            self._grid_lines.append(self.canvas.create_line(
                x, self._plot_top, x, self._plot_bottom,
                fill=CHART_GRID, dash=(2, 4)))

        # Axis labels (Y: torque, X: rpm)
        for i in range(GRID_DIVISIONS + 1):
            frac = i / GRID_DIVISIONS
            y = self._plot_bottom - frac * plot_h
            self._axis_labels.append(self.canvas.create_text(
                self._plot_left - 5, y, text='', anchor='e',
                fill=CHART_TEXT, font=('Consolas', 7)))
            x = self._plot_left + frac * plot_w
            self._axis_labels.append(self.canvas.create_text(
                x, self._plot_bottom + 5, text='', anchor='n',
                fill=CHART_TEXT, font=('Consolas', 7)))

        # Axis titles
        self._x_title = self.canvas.create_text(
            (self._plot_left + self._plot_right) / 2, h - 3,
            text='RPM (r/m)', fill=CHART_AXIS, font=('Consolas', 8), anchor='s')
        self._y_title = self.canvas.create_text(
            8, (self._plot_top + self._plot_bottom) / 2,
            text='Torque (Nm)', fill=CHART_AXIS, font=('Consolas', 8),
            anchor='center', angle=90)
        self._chart_title = self.canvas.create_text(
            (self._plot_left + self._plot_right) / 2, 3,
            text='TORQUE vs RPM', fill=CHART_TITLE,
            font=('Consolas', 9, 'bold'), anchor='n')

        # Gear curve lines + legends (up to DEFAULT_MAX_GEAR)
        for g in range(1, DEFAULT_MAX_GEAR + 1):
            color = GEAR_COLORS[(g - 1) % len(GEAR_COLORS)]
            self._gear_lines[g] = self.canvas.create_line(
                0, 0, 0, 0, fill=color, width=1.5, smooth=True, state='hidden')
            legend_y = self._plot_top + 5 + (g - 1) * 14
            self._gear_legends[g] = self.canvas.create_text(
                self._plot_right + 5, legend_y, text=f'G{g}', fill=color,
                font=('Consolas', 8, 'bold'), anchor='nw', state='hidden')

        # Shift point lines (up to DEFAULT_MAX_GEAR - 1)
        for g in range(1, DEFAULT_MAX_GEAR):
            self._shift_lines[g] = self.canvas.create_line(
                0, self._plot_top, 0, self._plot_bottom,
                fill=SHIFT_COLOR, width=1, dash=(4, 4), state='hidden')

        # Cursor
        self._cursor_vline = self.canvas.create_line(
            0, self._plot_top, 0, self._plot_bottom,
            fill=CURSOR_COLOR, width=1, dash=(2, 2), state='hidden')
        self._cursor_dot = self.canvas.create_oval(
            0, 0, 0, 0, fill=CURSOR_COLOR, outline=ACTIVE_GLOW,
            width=2, state='hidden')
        self._cursor_readout = self.canvas.create_text(
            0, 0, text='', fill=CURSOR_COLOR,
            font=('Consolas', 7), anchor='sw', state='hidden')

        # Placeholder
        self._placeholder = self.canvas.create_text(
            (self._plot_left + self._plot_right) / 2,
            (self._plot_top + self._plot_bottom) / 2,
            text=PLACEHOLDER_TEXT[self._lang_index],
            fill=CHART_TEXT, font=('Consolas', 10), anchor='center')

        self._update_axis_labels()

        # Apply deferred analysis if needed
        if self._pending_forza is not None:
            self.update_from_analysis(self._pending_forza)
            self._pending_forza = None

    def _update_axis_labels(self):
        for i in range(GRID_DIVISIONS + 1):
            frac = i / GRID_DIVISIONS
            y_val = self._y_min + frac * (self._y_max - self._y_min)
            self.canvas.itemconfig(self._axis_labels[i * 2], text=f'{y_val:.0f}')
            x_val = self._x_min + frac * (self._x_max - self._x_min)
            self.canvas.itemconfig(self._axis_labels[i * 2 + 1], text=f'{x_val:.0f}')

    def _data_to_pixel(self, x_data, y_data):
        x_range = self._x_max - self._x_min
        y_range = self._y_max - self._y_min
        plot_w = self._plot_right - self._plot_left
        plot_h = self._plot_bottom - self._plot_top

        px = self._plot_left + (x_data - self._x_min) / x_range * plot_w if x_range else self._plot_left
        py = self._plot_bottom - (y_data - self._y_min) / y_range * plot_h if y_range else self._plot_top
        return px, py

    def update_from_analysis(self, forza):
        if not self._items_created:
            self._pending_forza = forza
            return
        if len(forza.gear_ratios) == 0:
            return

        self.canvas.itemconfig(self._placeholder, state='hidden')
        self._analysis_loaded = True

        # Compute data ranges
        all_rpms, all_torques = [], []
        for g in sorted(forza.gear_ratios.keys()):
            if g not in forza.rpm_torque_map:
                continue
            rpm_range = forza.rpm_torque_map[g]
            raw = forza.get_gear_raw_records(g)
            if not raw:
                continue
            ratio = forza.gear_ratios[g]['ratio']
            if ratio <= 0:
                continue
            for r in raw[rpm_range['min_rpm_index']:rpm_range['max_rpm_index']]:
                all_rpms.append(r['rpm'])
                all_torques.append(r['torque'] / ratio)

        if not all_rpms:
            return

        self._x_min = min(all_rpms) * 0.9
        self._x_max = max(all_rpms) * 1.05
        self._y_min = 0
        self._y_max = max(all_torques) * 1.15
        self._update_axis_labels()

        # Draw gear curves
        for g in range(1, DEFAULT_MAX_GEAR + 1):
            if g not in forza.gear_ratios or g not in forza.rpm_torque_map:
                self.canvas.itemconfig(self._gear_lines[g], state='hidden')
                self.canvas.itemconfig(self._gear_legends[g], state='hidden')
                continue

            rpm_range = forza.rpm_torque_map[g]
            raw = forza.get_gear_raw_records(g)
            ratio = forza.gear_ratios[g]['ratio']
            if not raw or ratio <= 0:
                continue

            records = raw[rpm_range['min_rpm_index']:rpm_range['max_rpm_index']]
            if len(records) < 2:
                continue

            records.sort(key=lambda r: r['rpm'])
            coords = []
            for r in records:
                px, py = self._data_to_pixel(r['rpm'], r['torque'] / ratio)
                coords.extend([px, py])

            self.canvas.coords(self._gear_lines[g], *coords)
            self.canvas.itemconfig(self._gear_lines[g], state='normal')
            self.canvas.itemconfig(self._gear_legends[g], state='normal')

        # Draw shift point lines
        for g in range(1, DEFAULT_MAX_GEAR):
            if g in self._shift_lines:
                if g in forza.shift_point:
                    px, _ = self._data_to_pixel(forza.shift_point[g]['rpmo'], 0)
                    self.canvas.coords(self._shift_lines[g], px, self._plot_top, px, self._plot_bottom)
                    self.canvas.itemconfig(self._shift_lines[g], state='normal')
                else:
                    self.canvas.itemconfig(self._shift_lines[g], state='hidden')

    def update_live_cursor(self, rpm, output_torque, gear):
        if not self._items_created:
            return

        # RPM vertical line (always shown when running)
        px, _ = self._data_to_pixel(rpm, 0)
        self.canvas.coords(self._cursor_vline, px, self._plot_top, px, self._plot_bottom)
        self.canvas.itemconfig(self._cursor_vline, state='normal')

        # Torque dot + readout (only with analysis data)
        if self._analysis_loaded and output_torque is not None:
            _, py = self._data_to_pixel(rpm, output_torque)
            r = DOT_RADIUS
            self.canvas.coords(self._cursor_dot, px - r, py - r, px + r, py + r)
            self.canvas.itemconfig(self._cursor_dot, state='normal')
            self.canvas.coords(self._cursor_readout, min(px + 5, self._plot_right - 60), py - 5)
            self.canvas.itemconfig(self._cursor_readout,
                                   text=f'{rpm:.0f}rpm {output_torque:.0f}Nm G{gear}',
                                   state='normal')
        else:
            self.canvas.itemconfig(self._cursor_dot, state='hidden')
            self.canvas.itemconfig(self._cursor_readout, state='hidden')

        # Highlight active gear
        if self._active_gear != gear:
            if self._active_gear in self._gear_lines and self._active_gear > 0:
                self.canvas.itemconfig(self._gear_lines[self._active_gear], width=1.5)
            if gear in self._gear_lines:
                self.canvas.itemconfig(self._gear_lines[gear], width=3)
            self._active_gear = gear

    def set_language(self, lang_index):
        self._lang_index = lang_index
        if self._items_created and not self._analysis_loaded:
            self.canvas.itemconfig(self._placeholder, text=PLACEHOLDER_TEXT[lang_index])

    def reset(self):
        if not self._items_created:
            return
        for line_id in self._gear_lines.values():
            self.canvas.itemconfig(line_id, state='hidden')
        for text_id in self._gear_legends.values():
            self.canvas.itemconfig(text_id, state='hidden')
        for line_id in self._shift_lines.values():
            self.canvas.itemconfig(line_id, state='hidden')
        self.canvas.itemconfig(self._cursor_vline, state='hidden')
        self.canvas.itemconfig(self._cursor_dot, state='hidden')
        self.canvas.itemconfig(self._cursor_readout, state='hidden')
        self.canvas.itemconfig(self._placeholder, text=PLACEHOLDER_TEXT[self._lang_index], state='normal')
        self._analysis_loaded = False
        self._active_gear = -1
