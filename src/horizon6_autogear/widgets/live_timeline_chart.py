"""Scrolling timeline chart using Tkinter Canvas pre-build pattern."""

import tkinter
from collections import deque

# Chart colors (glass theme)
CHART_BG = '#0d0d1a'
CHART_GRID = '#252550'
CHART_TEXT = '#8888bb'

# Chart margins (pixels)
MARGIN_LEFT = 40
MARGIN_RIGHT = 10
MARGIN_TOP = 12
MARGIN_BOTTOM = 14


class LiveTimelineChart:
    """Generic scrolling timeline chart with multiple series.

    Pre-builds Canvas items, updates via coords()/itemconfig().
    Data scrolls left as new points are pushed.
    """

    def __init__(self, canvas: tkinter.Canvas, series_config: list, max_points: int = 150):
        self.canvas = canvas
        self._items_created = False
        self._max_points = max_points
        self._series_config = series_config

        # Data storage per series
        self._data = [deque(maxlen=max_points) for _ in series_config]

        # Plot area bounds
        self._plot_left = 0
        self._plot_top = 0
        self._plot_right = 0
        self._plot_bottom = 0

        # Canvas item IDs
        self._grid_lines = []
        self._series_lines = []
        self._legend_texts = []
        self._title = None

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

        plot_w = self._plot_right - self._plot_left

        # Vertical grid lines (5 divisions)
        for i in range(6):
            x = self._plot_left + i * plot_w / 5
            self._grid_lines.append(self.canvas.create_line(
                x, self._plot_top, x, self._plot_bottom,
                fill=CHART_GRID, dash=(2, 4)))

        # Horizontal zero line
        mid_y = (self._plot_top + self._plot_bottom) / 2
        self._grid_lines.append(self.canvas.create_line(
            self._plot_left, mid_y, self._plot_right, mid_y,
            fill=CHART_GRID, width=1))

        # Series lines (initially flat at bottom)
        for cfg in self._series_config:
            line_id = self.canvas.create_line(
                self._plot_left, self._plot_bottom,
                self._plot_right, self._plot_bottom,
                fill=cfg['color'], width=1.2, smooth=False)
            self._series_lines.append(line_id)

        # Legend (top-left, stacked)
        for i, cfg in enumerate(self._series_config):
            text_id = self.canvas.create_text(
                self._plot_left + 4 + i * 70, self._plot_top - 1,
                text=cfg['name'], fill=cfg['color'],
                font=('Consolas', 7), anchor='sw')
            self._legend_texts.append(text_id)

    def push(self, values: list):
        """Push new data point for each series and redraw."""
        if not self._items_created:
            return

        for i, v in enumerate(values):
            if i < len(self._data):
                self._data[i].append(v)

        self._redraw()

    def reset(self):
        """Clear all data and redraw empty."""
        for d in self._data:
            d.clear()
        if self._items_created:
            self._redraw()

    def _redraw(self):
        plot_w = self._plot_right - self._plot_left
        plot_h = self._plot_bottom - self._plot_top
        if plot_w <= 0 or plot_h <= 0:
            return

        for i, cfg in enumerate(self._series_config):
            data = self._data[i]
            if len(data) < 2:
                self.canvas.coords(self._series_lines[i],
                                   self._plot_left, self._plot_bottom,
                                   self._plot_right, self._plot_bottom)
                continue

            max_val = cfg['max_val']
            n = len(data)
            coords = []
            for j, v in enumerate(data):
                x = self._plot_left + j / max(n - 1, 1) * plot_w
                y = self._plot_bottom - (v / max_val * plot_h)
                # Clamp to plot area
                y = max(self._plot_top, min(self._plot_bottom, y))
                coords.extend([x, y])

            self.canvas.coords(self._series_lines[i], *coords)
