# Glassmorphism-style GUI for Horizon6AutoGear
# Same business logic as gui.py, with modern glassmorphism visual design

import math
import os
import tkinter
import tkinter.ttk
import warnings
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from tkinter import scrolledtext

import matplotlib.colors as mcolors
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from pynput.keyboard import Listener

import horizon6_autogear.config.config as constants
import horizon6_autogear.utils.helper as helper
import horizon6_autogear.shifting.keyboard as keyboard_helper
from horizon6_autogear.core.forza import Forza
from horizon6_autogear.core.recorder import Recorder
from horizon6_autogear.core.playback import PlaybackSource
from horizon6_autogear.utils.logger import Logger, TextHandler
from horizon6_autogear.widgets.live_torque_chart import LiveTorqueChart
from horizon6_autogear.widgets.live_timeline_chart import LiveTimelineChart
from horizon6_autogear.widgets.hud_overlay import CoachHUD

warnings.filterwarnings("ignore", category=UserWarning)

# === Glassmorphism Theme Colors ===
GLASS_BG = "#0f0c29"
GLASS_CARD = "#1a1a3e"
GLASS_CARD_LIGHT = "#252550"
GLASS_BORDER = "#3a3a6e"
GLASS_TEXT = "#e0e0ff"
GLASS_TEXT_DIM = "#8888bb"
GLASS_ACCENT = "#667eea"
GLASS_ACCENT2 = "#764ba2"
GLASS_GREEN = "#00ff88"
GLASS_CYAN = "#00d4ff"
GLASS_RED = "#ff4466"
GLASS_YELLOW = "#ffdd00"
GLASS_LOG_BG = "#0d0d1a"
GLASS_LOG_FG = "#00ff88"
GLASS_CHART_BG = "#0d0d1a"
GLASS_CHART_FACE = "#1a1a3e"
GLASS_CHART_GRID = "#2a2a4e"

# Arc gauge constants
GAUGE_ARC_WIDTH = 10
GAUGE_START_ANGLE = 225
GAUGE_FULL_EXTENT = 270


class GlassWindow:

    def __init__(self):
        self.root = tkinter.Tk()

        # init text
        self.language = helper.get_sys_lang()
        self.init_text()
        self.text_update(self.language)

        # Layout
        self.root.grid_rowconfigure(0, minsize=500, weight=500)
        self.root.grid_rowconfigure(1, minsize=300, weight=300)
        self.root.grid_columnconfigure(0, minsize=130, weight=1)    # Left: settings ~10%
        self.root.grid_columnconfigure(1, minsize=650, weight=8)    # Center: display ~74%
        self.root.grid_columnconfigure(2, minsize=200, weight=2)    # Right: static ~16%

        self.root.title("Forza Horizon 5: Auto Gear Shifting - Glass Edition")
        self.root.geometry("1300x800")
        self.root.minsize(1200, 800)
        # No maxsize limit — supports 4K and above
        self.root["background"] = GLASS_BG

        # State variables
        self.speed_tree = {}
        self.rpm_tree = {}

        self.car_id_var = tkinter.StringVar()
        self.car_id_var.set("None")
        self.car_perf_var = tkinter.IntVar()
        self.car_perf_var.set(0)
        self.car_class_var = tkinter.IntVar()
        self.car_class_var.set(-1)
        self.car_drivetrain_var = tkinter.StringVar()
        self.car_drivetrain_var.set('N')

        self.tires = {}
        self.tire_slip_text = {}
        self.tire_temp_text = {}
        self.tire_susp_bar = {}
        self.tire_color = mcolors.LinearSegmentedColormap.from_list(
            "tire_slip", [(0, "#00ff88"), (0.4, "#aaff00"), (0.7, "#ffdd00"), (1.0, "#ff4466")]
        )
        self.chart_figure = None
        self.chart_canvas_widget = None

        self.acceleration_var = tkinter.StringVar()
        self.acceleration_var.set("0%")
        self.brake_var = tkinter.StringVar()
        self.brake_var.set("0%")

        # Real-time telemetry state
        self.gforce_trail = deque(maxlen=120)
        self._last_gear = 0

        # Coach HUD
        self.coach_mode = False
        self.coach_hud = None

        # Build UI
        self.set_bottom_area()

        self.threadPool = ThreadPoolExecutor(max_workers=constants.MAX_WORKER_THREADS, thread_name_prefix=constants.THREAD_NAME_PREFIX)
        self.engine = Forza(self.threadPool, self.logger, constants.PACKET_FORMAT, enable_clutch=constants.ENABLE_CLUTCH)
        self.listener = Listener(on_press=self.on_press)

        self.set_car_setting_frame()
        self.set_car_perf_frame()
        self.set_right_frame()
        self.set_button_frame()
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.logger.info('Forza Horizon 5: Auto Gear Shifting Started - Glass Edition!')
        self.listener.start()
        self.root.mainloop()

    # ---- Text / i18n (identical logic to gui.py) ----

    def init_text(self):
        self.select_language_txt = tkinter.StringVar()
        self.language_txt = tkinter.StringVar()
        self.clutch_shortcut_txt = tkinter.StringVar()
        self.upshift_shortcut_txt = tkinter.StringVar()
        self.downshift_shortcut_txt = tkinter.StringVar()
        self.clutch_txt = tkinter.StringVar()
        self.farm_txt = tkinter.StringVar()
        self.offroad_rally_txt = tkinter.StringVar()
        self.car_id = tkinter.StringVar()
        self.car_perf = tkinter.StringVar()
        self.car_drivetrain = tkinter.StringVar()
        self.tire_information_txt = tkinter.StringVar()
        self.accel_txt = tkinter.StringVar()
        self.brake_txt = tkinter.StringVar()
        self.shift_point_txt = tkinter.StringVar()
        self.tree_value_txt = tkinter.StringVar()
        self.speed_txt = tkinter.StringVar()
        self.rpm_txt = tkinter.StringVar()
        self.collect_button_txt = tkinter.StringVar()
        self.analysis_button_txt = tkinter.StringVar()
        self.run_button_txt = tkinter.StringVar()
        self.pause_button_txt = tkinter.StringVar()
        self.exit_button_txt = tkinter.StringVar()
        self.clear_log_text = tkinter.StringVar()
        self.log_tab_txt = tkinter.StringVar()
        self.charts_tab_txt = tkinter.StringVar()
        self.record_button_txt = tkinter.StringVar()
        self.playback_button_txt = tkinter.StringVar()
        self.shift_point_tab_txt = tkinter.StringVar()
        self.live_torque_tab_txt = tkinter.StringVar()

    def text_update(self, lang_index):
        self.select_language_txt.set(constants.SELECT_LANGUAGE_TXT[lang_index])
        self.language_txt.set(constants.LANGUAGE_TXT[lang_index])
        self.clutch_shortcut_txt.set(constants.CLUTCH_SHORTCUT_TXT[lang_index])
        self.upshift_shortcut_txt.set(constants.UPSHIFT_SHORTCUT_TXT[lang_index])
        self.downshift_shortcut_txt.set(constants.DOWNSHIFT_SHORTCUT_TXT[lang_index])
        self.clutch_txt.set(constants.CLUTCH_TXT[lang_index])
        self.farm_txt.set(constants.FARM_TXT[lang_index])
        self.offroad_rally_txt.set(constants.OFFROAD_RALLY_TXT[lang_index])
        self.car_id.set(constants.CAR_ID[lang_index])
        self.car_perf.set(constants.CAR_PERF[lang_index])
        self.car_drivetrain.set(constants.CAR_DRIVETRAIN[lang_index])
        self.tire_information_txt.set(constants.TIRE_INFORMATION_TXT[lang_index])
        self.accel_txt.set(constants.ACCEL_TXT[lang_index])
        self.brake_txt.set(constants.BRAKE_TXT[lang_index])
        self.shift_point_txt.set(constants.SHIFT_POINT_TXT[lang_index])
        self.tree_value_txt.set(constants.TREE_VALUE_TXT[lang_index])
        self.speed_txt.set(f'{constants.SPEED_TXT[lang_index]} km/h')
        self.rpm_txt.set(f'{constants.RPM_TXT[lang_index]} r/m')
        self.collect_button_txt.set(f'{constants.COLLECT_BUTTON_TXT[lang_index]} ({constants.COLLECT_DATA.name})')
        self.analysis_button_txt.set(f'{constants.ANALYSIS_BUTTON_TXT[lang_index]} ({constants.ANALYSIS.name})')
        self.run_button_txt.set(f'{constants.RUN_BUTTON_TXT[lang_index]} ({constants.AUTO_SHIFT.name})')
        self.pause_button_txt.set(f'{constants.PAUSE_BUTTON_TXT[lang_index]} ({constants.STOP.name})')
        self.exit_button_txt.set(f'{constants.EXIT_BUTTON_TXT[lang_index]} ({constants.CLOSE.name})')
        self.clear_log_text.set(constants.CLEAR_LOG_TXT[lang_index])
        self.log_tab_txt.set(['Log', '日志'][lang_index])
        self.charts_tab_txt.set(['Charts', '图表'][lang_index])
        self.record_button_txt.set(constants.RECORD_TXT[lang_index])
        self.playback_button_txt.set(constants.PLAYBACK_TXT[lang_index])
        self.shift_point_tab_txt.set(['Shift Points', '换挡点'][lang_index])
        self.live_torque_tab_txt.set(constants.LIVE_TORQUE_TAB_TXT[lang_index])

        # Card titles (replaces old notebook tab labels)
        if hasattr(self, 'shift_card_title'):
            self.shift_card_title.configure(text=self.shift_point_tab_txt.get())
        if hasattr(self, 'charts_card_title'):
            self.charts_card_title.configure(text=self.charts_tab_txt.get())
        if hasattr(self, 'live_card_title'):
            self.live_card_title.configure(text=self.live_torque_tab_txt.get())
        if hasattr(self, 'log_card_title'):
            self.log_card_title.configure(text=self.log_tab_txt.get())
        if hasattr(self, 'program_info'):
            self.program_info.configure(text=constants.PROGRAM_INFO_TXT[lang_index])

        if hasattr(self, 'live_torque_chart'):
            self.live_torque_chart.set_language(lang_index)

        if hasattr(self, 'coach_mode_txt_var'):
            self.coach_mode_txt_var.set(constants.COACH_MODE_TXT[lang_index])

        if hasattr(self, 'tire_canvas'):
            self.tire_canvas.itemconfigure(self.tire_canvas_text, text=self.tire_information_txt.get())

        if hasattr(self, '_shift_headers'):
            header_texts = [self.shift_point_txt.get(), self.speed_txt.get(), self.rpm_txt.get()]
            for i, lbl in enumerate(self._shift_headers):
                lbl.configure(text=header_texts[i], fg=GLASS_TEXT_DIM)

    # ---- Data update methods ----

    def update_tree(self):
        last_key = 0
        for key, value in self.engine.shift_point.items():
            if key in self.speed_tree:
                self.speed_tree[key].config(text=f"{value['speed']:.1f}")
                self.rpm_tree[key].config(text=f"{value['rpmo']:.0f}")
                last_key = max(last_key, key)
        for i in range(last_key + 1, 11):
            self.speed_tree[i].config(text='-')
            self.rpm_tree[i].config(text='-')

    def update_car_info(self, fdp):
        """Thread-safe car info update - captures data on worker thread,
        schedules widget updates on main thread via after_idle."""
        if not self.engine.isRunning:
            return

        # Capture data immediately on worker thread
        data = {
            'car_ordinal': fdp.car_ordinal,
            'car_perf': fdp.car_performance_index,
            'car_class': fdp.car_class,
            'drivetrain': fdp.drivetrain_type,
            'accel': fdp.accel,
            'brake': fdp.brake,
            'speed': fdp.speed * constants.MS_TO_KMH,
            'rpm': fdp.current_engine_rpm,
            'gear': fdp.gear,
            'engine_max_rpm': fdp.engine_max_rpm,
            'accel_x': fdp.acceleration_x,
            'accel_z': fdp.acceleration_z,
            'slips': {pos: abs(getattr(fdp, attr)) for pos, attr in [
                ("FL", "tire_combined_slip_FL"), ("FR", "tire_combined_slip_FR"),
                ("RL", "tire_combined_slip_RL"), ("RR", "tire_combined_slip_RR")
            ]},
            'tire_temps': {
                'FL': fdp.tire_temp_FL, 'FR': fdp.tire_temp_FR,
                'RL': fdp.tire_temp_RL, 'RR': fdp.tire_temp_RR
            },
            'susp_travel': {
                'FL': fdp.norm_suspension_travel_FL, 'FR': fdp.norm_suspension_travel_FR,
                'RL': fdp.norm_suspension_travel_RL, 'RR': fdp.norm_suspension_travel_RR
            },
            'boost': fdp.boost,
            'fuel': fdp.fuel,
            'torque': fdp.torque,
            'norm_driving_line': fdp.norm_driving_line,
            'norm_ai_brake_diff': fdp.norm_ai_brake_diff,
        }
        self.root.after_idle(lambda: self._update_car_info_widgets(data))

    def _update_car_info_widgets(self, data):
        """Update Tkinter widgets on the main thread. Called via root.after_idle."""
        if not self.engine.isRunning:
            return

        self.car_id_var.set(data['car_ordinal'])
        self.car_perf_var.set(data['car_perf'])
        self.car_class_var.set(data['car_class'])
        self.car_drivetrain_var.set(constants.CAR_DRIVETRAIN_LIST[data['drivetrain']][self.language])

        self.perf_canvas.config(bg=constants.CAR_CLASS_COLOR[data['car_class']])
        self.perf_canvas.itemconfig(self.car_class_text, text=constants.CAR_CLASS_LIST[data['car_class']])
        self.perf_index_canvas.itemconfig(self.perf_index_text, text=data['car_perf'])

        self.acceleration_var.set(f"{round(data['accel'] / constants.FORZA_INPUT_MAX * 100, 1)}%")
        self.brake_var.set(f"{round(data['brake'] / constants.FORZA_INPUT_MAX * 100, 1)}%")

        for pos, slip in data['slips'].items():
            clamped = min(slip, 1.0)
            temp = data['tire_temps'].get(pos, 0)
            travel = data['susp_travel'].get(pos, 0)

            # Color tire box by temperature (continuous scale per spec)
            if temp <= 0:
                tire_fill = GLASS_CARD_LIGHT
            else:
                tire_fill = self._tire_temp_color(temp)
            self.tire_canvas.itemconfig(self.tires[pos], fill=tire_fill)

            # Slip visual feedback per spec thresholds
            if clamped > 0.15:
                self.tire_canvas.itemconfig(self.tires[pos], outline=GLASS_RED)
                slip_text_color = GLASS_RED
            elif clamped > 0.08:
                self.tire_canvas.itemconfig(self.tires[pos], outline=GLASS_YELLOW)
                slip_text_color = GLASS_YELLOW
            else:
                self.tire_canvas.itemconfig(self.tires[pos], outline=GLASS_BORDER)
                slip_text_color = GLASS_GREEN
            if pos in self.tire_slip_text:
                self.tire_canvas.itemconfig(self.tire_slip_text[pos],
                                            text=f"{slip:.2f}", fill=slip_text_color)

            # Temperature text
            if pos in self.tire_temp_text:
                temp_str = f"{temp:.0f}°" if temp > 0 else "--"
                self.tire_canvas.itemconfig(self.tire_temp_text[pos], text=temp_str)

            # Suspension bar
            if pos in self.tire_susp_bar:
                travel_clamped = max(0.0, min(1.0, travel))
                # Get the bar's parent rect coords for width reference
                tire_id = self.tires[pos]
                coords = self.tire_canvas.coords(tire_id)
                if coords and len(coords) >= 4:
                    box_w = coords[2] - coords[0] - 4
                    fill_w = travel_clamped * box_w
                    x0 = coords[0] + 2
                    y0 = coords[1] + 3
                    susp_color = GLASS_RED if travel > 0.8 else (GLASS_YELLOW if travel > 0.6 else GLASS_GREEN)
                    self.tire_canvas.coords(self.tire_susp_bar[pos], x0, y0, x0 + fill_w, y0 + 3)
                    self.tire_canvas.itemconfig(self.tire_susp_bar[pos], fill=susp_color)

        # Real-time gauges and G-force
        self._update_speed_gauge(data['speed'])
        self._update_rpm_gauge(data['rpm'], data['engine_max_rpm'])
        self._update_gear_display(data['gear'])
        self._update_pedal_bars(data['accel'], data['brake'])
        self._update_gforce(data['accel_x'], data['accel_z'])
        self._update_boost_fuel(data.get('boost', 0), data.get('fuel', 1))
        self._update_live_torque(data)
        self._update_rpm_speed_timeline(data)
        self._update_gforce_trace(data)
        self._update_coach_hud(data)
        self.root.update_idletasks()

    def reset_car_info(self):
        for key, _ in self.speed_tree.items():
            self.speed_tree[key].config(text='-')
            self.rpm_tree[key].config(text='-')
        self.acceleration_var.set("0.0%")
        self.brake_var.set("0.0%")
        for pos in ["FL", "FR", "RL", "RR"]:
            self.tire_canvas.itemconfig(self.tires[pos], fill=GLASS_CARD, outline=GLASS_BORDER)
            if pos in self.tire_slip_text:
                self.tire_canvas.itemconfig(self.tire_slip_text[pos],
                                            text="0.00", fill=GLASS_TEXT)
            if pos in self.tire_temp_text:
                self.tire_canvas.itemconfig(self.tire_temp_text[pos], text="--")
            if pos in self.tire_susp_bar:
                coords = self.tire_canvas.coords(self.tires[pos])
                if coords and len(coords) >= 4:
                    self.tire_canvas.coords(self.tire_susp_bar[pos],
                                            coords[0] + 2, coords[1] + 3,
                                            coords[0] + 2, coords[1] + 3)

        # Reset gauges
        self._update_speed_gauge(0)
        self._update_rpm_gauge(0, 9000)
        self._update_gear_display(0)
        self._update_pedal_bars(0, 0)
        self._update_boost_fuel(0, 1)

        # Reset live torque chart
        if hasattr(self, 'live_torque_chart'):
            self.live_torque_chart.reset()
        if hasattr(self, 'rpm_speed_chart'):
            self.rpm_speed_chart.reset()
        if hasattr(self, 'gforce_trace_chart'):
            self.gforce_trace_chart.reset()

        # Cancel pending gear glow
        if getattr(self, '_gear_flash_id', None) is not None and self.root.winfo_exists():
            try:
                self.root.after_cancel(self._gear_flash_id)
            except ValueError:
                pass
            self._gear_flash_id = None

        # Reset G-force
        self.gforce_trail.clear()
        if hasattr(self, 'gforce_dot'):
            self.gforce_canvas.coords(self.gforce_trail_line, 0, 0, 0, 0)
            self.gforce_canvas.coords(self.gforce_dot,
                                      self._gforce_cx - 3, self._gforce_cy - 3,
                                      self._gforce_cx + 3, self._gforce_cy + 3)
            self.gforce_canvas.itemconfig(self.gforce_dot, fill=GLASS_GREEN)
            self.gforce_canvas.itemconfig(self.gforce_text, text="0.00G")

    def on_press(self, key):
        try:
            if key == constants.COLLECT_DATA:
                self.collect_data_handler(None)
            elif key == constants.ANALYSIS:
                self.analysis_handler(None, performance_profile=False, is_guid=False)
            elif key == constants.AUTO_SHIFT:
                self.run_handler(None)
            elif key == constants.STOP:
                self.pause_handler(None)
            elif key == constants.CLOSE:
                self.exit_handler(None)
        except BaseException as e:
            self.engine.logger.exception(e)

    def close(self):
        self.engine.isRunning = False
        # Close socket to unblock any pending recvfrom() immediately
        if hasattr(self.engine, 'server_socket'):
            helper.close_socket(self.engine)
        self.listener.stop()
        if self.coach_hud is not None:
            self.coach_hud.destroy()
        self.root.destroy()
        self.threadPool.shutdown(wait=False)

    # ---- UI Layout: Glass card helper ----

    def _glass_frame(self, parent, **grid_kw):
        """Create a frame with glassmorphism card style."""
        f = tkinter.Frame(parent, border=0, bg=GLASS_CARD, relief="groove",
                          highlightthickness=1, highlightbackground=GLASS_BORDER,
                          highlightcolor=GLASS_BORDER)
        if grid_kw:
            grid_kw.setdefault('sticky', 'news')
            f.grid(**grid_kw)
        return f

    def _glass_label(self, parent, **kw):
        kw.setdefault('fg', GLASS_TEXT)
        kw.setdefault('font', ('Segoe UI', 10))
        return tkinter.Label(parent, bg=GLASS_CARD, **kw)

    # ---- Settings panel (left column, row 0) ----

    def get_rely(self, count):
        return constants.SETTINGS_WIDGET_START_Y + constants.SETTINGS_WIDGET_SPACING * count

    def place_languages(self, pre_widget_count=0):
        language_label = self._glass_label(self.car_info_frame, textvariable=self.select_language_txt)
        language_label.place(relx=0.06, rely=self.get_rely(pre_widget_count), anchor="w")
        pre_widget_count += 1

        style = tkinter.ttk.Style()
        style.configure("Glass.TCombobox", fieldbackground=GLASS_CARD_LIGHT,
                         background=GLASS_CARD_LIGHT, foreground=GLASS_TEXT)

        language_combobox = tkinter.ttk.Combobox(self.car_info_frame, values=constants.LANGUAGE_TXT,
                                                   state='readonly', style="Glass.TCombobox")
        language_combobox.current(self.language)

        def set_language(event):
            self.language = constants.LANGUAGE_TXT.index(event.widget.get())
            self.text_update(self.language)

        language_combobox.bind("<<ComboboxSelected>>", set_language)
        language_combobox.place(relx=0.08, rely=self.get_rely(pre_widget_count), anchor="w")
        return pre_widget_count + 1

    def place_ip_port(self, pre_widget_count=0):
        for label_text, value in [("IP", self.engine.ip), ("Port", self.engine.port)]:
            w = tkinter.Text(self.car_info_frame, borderwidth=0, bg=GLASS_CARD,
                             fg=GLASS_CYAN, wrap=tkinter.WORD, font=('Consolas', 9),
                             height=1)
            w.insert("1.0", f'{label_text}: {value}')
            w.place(relx=0.08, rely=self.get_rely(pre_widget_count), relwidth=0.85, relheight=0.03, anchor="w")
            w.configure(state="disabled")
            pre_widget_count += 1
        return pre_widget_count

    def place_shortcuts(self, pre_widget_count=0):
        def get_available_shortcuts(cur_shortcut):
            all_boundKeys = self.engine.boundKeys()
            all_boundKeys.extend(constants.BOUND_KEYS)
            return [x for x in keyboard_helper.key_list if x not in all_boundKeys or x == cur_shortcut]

        shortcut_list = []
        for label_var, attr in [(self.clutch_shortcut_txt, "clutch"),
                                (self.upshift_shortcut_txt, "upshift"),
                                (self.downshift_shortcut_txt, "downshift")]:
            lbl = self._glass_label(self.car_info_frame, textvariable=label_var)
            shortcut_list.append((lbl, ""))

            shortcuts = get_available_shortcuts(getattr(self.engine, attr))
            cb = tkinter.ttk.Combobox(self.car_info_frame, values=shortcuts, state='readonly',
                                       style="Glass.TCombobox")
            cb.current(shortcuts.index(getattr(self.engine, attr)))
            shortcut_list.append((cb, attr))

        all_combobox = [box[0] for box in shortcut_list if isinstance(box[0], tkinter.ttk.Combobox)]

        for i, (widget, attr_name) in enumerate(shortcut_list):
            if isinstance(widget, tkinter.Label):
                widget.place(relx=0.06, rely=self.get_rely(i + pre_widget_count), anchor="w")
            elif isinstance(widget, tkinter.ttk.Combobox):
                def set_shortcut(event, _attr=attr_name):
                    setattr(self.engine, _attr, event.widget.get())
                    self.logger.info(f"{_attr} shortcut is: {event.widget.get()}")
                    for box in all_combobox:
                        box['values'] = get_available_shortcuts(box.get())

                widget.bind("<<ComboboxSelected>>", set_shortcut)
                widget.place(relx=0.08, rely=self.get_rely(i + pre_widget_count), anchor="w")

        return len(shortcut_list) + pre_widget_count

    def set_car_setting_frame(self):
        self.car_info_frame = self._glass_frame(self.root, row=0, column=0)
        total_widget = 0

        total_widget = self.place_ip_port(total_widget)
        total_widget = self.place_languages(total_widget)
        total_widget = self.place_shortcuts(total_widget)

        # Clutch
        enable_clutch = tkinter.IntVar(value=self.engine.enable_clutch)

        def set_clutch():
            self.engine.enable_clutch = enable_clutch.get()

        tkinter.Checkbutton(self.car_info_frame, textvariable=self.clutch_txt, onvalue=1, offvalue=0,
                            variable=enable_clutch, bg=GLASS_CARD, fg=GLASS_TEXT, selectcolor=GLASS_CARD_LIGHT,
                            activebackground=GLASS_CARD, activeforeground=GLASS_TEXT,
                            command=set_clutch).place(relx=0.05, rely=self.get_rely(total_widget), anchor="w")
        total_widget += 1

        # Farm
        enable_farm = tkinter.IntVar(value=self.engine.farming)

        def set_farm():
            self.engine.farming = enable_farm.get()

        tkinter.Checkbutton(self.car_info_frame, textvariable=self.farm_txt, onvalue=1, offvalue=0,
                            variable=enable_farm, bg=GLASS_CARD, fg=GLASS_TEXT, selectcolor=GLASS_CARD_LIGHT,
                            activebackground=GLASS_CARD, activeforeground=GLASS_TEXT,
                            command=set_farm).place(relx=0.05, rely=self.get_rely(total_widget), anchor="w")
        total_widget += 1

        # Offroad/Rally
        enable_offroad_rally = tkinter.IntVar(value=0)

        def set_offroad_rally():
            self.engine.shift_point_factor = constants.OFFROAD_RALLY_SHIFT_FACTOR if enable_offroad_rally.get() == 1 else constants.SHIFT_FACTOR

        tkinter.Checkbutton(self.car_info_frame, textvariable=self.offroad_rally_txt, onvalue=1, offvalue=0,
                            variable=enable_offroad_rally, bg=GLASS_CARD, fg=GLASS_TEXT, selectcolor=GLASS_CARD_LIGHT,
                            activebackground=GLASS_CARD, activeforeground=GLASS_TEXT,
                            command=set_offroad_rally).place(relx=0.05, rely=self.get_rely(total_widget), anchor="w")
        total_widget += 1

        # Coach mode
        coach_var = tkinter.IntVar(value=0)

        def toggle_coach():
            self.coach_mode = coach_var.get() == 1
            if self.coach_mode:
                if self.coach_hud is None:
                    self.coach_hud = CoachHUD(self.root)
                self.coach_hud.show()
            elif self.coach_hud is not None:
                self.coach_hud.hide()

        coach_txt = tkinter.StringVar()
        coach_txt.set(constants.COACH_MODE_TXT[self.language])
        self.coach_mode_txt_var = coach_txt

        tkinter.Checkbutton(self.car_info_frame, textvariable=coach_txt,
                            onvalue=1, offvalue=0, variable=coach_var,
                            bg=GLASS_CARD, fg=GLASS_TEXT, selectcolor=GLASS_CARD_LIGHT,
                            activebackground=GLASS_CARD, activeforeground=GLASS_TEXT,
                            command=toggle_coach).place(
            relx=0.05, rely=self.get_rely(total_widget), anchor="w")

    # ---- Car performance panel (center column, row 0) ----
    # Layout: 3 sub-frames [car-info | gauges+pedals | tires+gforce]

    def set_car_perf_frame(self):
        self.car_perf_frame = self._glass_frame(self.root, row=0, column=1)
        self.car_perf_frame.update()

        # Sub-frame layout
        self.car_perf_frame.grid_columnconfigure(0, minsize=160, weight=0)
        self.car_perf_frame.grid_columnconfigure(1, weight=1)
        self.car_perf_frame.grid_columnconfigure(2, minsize=170, weight=0)
        self.car_perf_frame.grid_rowconfigure(0, weight=1)

        left_frame = tkinter.Frame(self.car_perf_frame, bg=GLASS_CARD)
        left_frame.grid(row=0, column=0, sticky='news')

        center_frame = tkinter.Frame(self.car_perf_frame, bg=GLASS_CARD)
        center_frame.grid(row=0, column=1, sticky='news')

        right_frame = tkinter.Frame(self.car_perf_frame, bg=GLASS_CARD)
        right_frame.grid(row=0, column=2, sticky='news')

        self._build_car_info_left(left_frame)
        self._build_gauges_center(center_frame)
        self._build_tires_gforce_right(right_frame)

    def _build_car_info_left(self, parent):
        """Left sub-frame: Car ID, Perf sticker, Drivetrain."""
        # Car ID
        self._glass_label(parent, textvariable=self.car_id,
                          font=('Segoe UI', 11, 'bold')).place(
            relx=0.08, rely=0.06, anchor=tkinter.W)

        self._glass_label(parent, textvariable=self.car_id_var,
                          font=('Segoe UI', 16, 'bold'), fg=GLASS_CYAN).place(
            relx=0.08, rely=0.13, anchor=tkinter.W)

        # Car perf label
        self._glass_label(parent, textvariable=self.car_perf,
                          font=('Segoe UI', 11, 'bold')).place(
            relx=0.08, rely=0.30, anchor=tkinter.W)

        # Perf sticker
        perf_width = 0.55
        perf_height = 0.07
        self.perf_canvas = tkinter.Canvas(parent,
                                          background=constants.CAR_CLASS_COLOR[self.engine.car_class],
                                          bd=0, highlightthickness=False)
        self.perf_canvas.place(relx=0.1, rely=0.37,
                               relwidth=perf_width, relheight=perf_height, anchor=tkinter.NW)
        self.car_class_text = self.perf_canvas.create_text(
            35, 12,
            text=constants.CAR_CLASS_LIST[self.engine.car_class],
            fill=constants.PERF_STICKER_BACKGROUND,
            font=('Segoe UI', 11, 'bold'), anchor=tkinter.CENTER)

        self.perf_index_canvas = tkinter.Canvas(parent,
                                                background=constants.PERF_STICKER_BACKGROUND,
                                                bd=0, highlightthickness=False)
        self.perf_index_canvas.place(relx=0.1 + perf_width * 0.6, rely=0.37 + 0.005,
                                     relwidth=0.3, relheight=0.055, anchor=tkinter.NW)
        self.perf_index_text = self.perf_index_canvas.create_text(
            12, 8,
            text=self.engine.car_perf, fill=constants.BACKGROUND_COLOR,
            font=('Segoe UI', 11, 'bold'), anchor=tkinter.CENTER)

        # Drivetrain
        self._glass_label(parent, textvariable=self.car_drivetrain,
                          font=('Segoe UI', 11, 'bold')).place(
            relx=0.08, rely=0.82, anchor=tkinter.SW)

        self._glass_label(parent, textvariable=self.car_drivetrain_var,
                          font=('Segoe UI', 16, 'bold'), fg=GLASS_CYAN).place(
            relx=0.08, rely=0.90, anchor=tkinter.SW)

    def _build_gauges_center(self, parent):
        """Center sub-frame: Speed gauge, Gear display, RPM gauge, Pedal bars.
        Canvas items are created on first <Configure> event when actual size is known."""
        self.gauge_canvas = tkinter.Canvas(parent, bg=GLASS_CARD, bd=0, highlightthickness=False)
        self.gauge_canvas.pack(fill='both', expand=True, padx=5, pady=5)
        self._gauge_items_created = False
        self.gauge_canvas.bind('<Configure>', self._on_gauge_configure)

    def _on_gauge_configure(self, event):
        """Create gauge Canvas items once the Canvas has been sized."""
        if self._gauge_items_created:
            return
        self._gauge_items_created = True
        c = self.gauge_canvas
        w, h = event.width, event.height
        if w < 50 or h < 100:
            return

        # === Speed Gauge (left third) ===
        gauge_size = min(w / 3, h * 0.45)
        sx1, sy1 = 10, 30
        sx2, sy2 = sx1 + gauge_size, sy1 + gauge_size
        self.speed_arc_bg = c.create_arc(
            sx1, sy1, sx2, sy2, start=GAUGE_START_ANGLE, extent=GAUGE_FULL_EXTENT,
            style='arc', outline=GLASS_CARD_LIGHT, width=GAUGE_ARC_WIDTH)
        # Gradient segments (10)
        seg_extent = GAUGE_FULL_EXTENT / 10
        self.speed_segments = []
        self._speed_prev_colors = [None] * 10
        for i in range(10):
            seg = c.create_arc(
                sx1, sy1, sx2, sy2,
                start=GAUGE_START_ANGLE + i * seg_extent, extent=seg_extent,
                style='arc', outline=GLASS_GREEN, width=GAUGE_ARC_WIDTH, state='hidden')
            self.speed_segments.append(seg)
        scx, scy = (sx1 + sx2) / 2, (sy1 + sy2) / 2 + gauge_size * 0.06
        self.speed_value_text = c.create_text(
            scx, scy - 5, text="0", fill=GLASS_GREEN,
            font=('Segoe UI', max(16, int(gauge_size * 0.17)), 'bold'), anchor=tkinter.CENTER)
        c.create_text(scx, scy + gauge_size * 0.12, text="km/h", fill=GLASS_TEXT_DIM,
                      font=('Segoe UI', 8), anchor=tkinter.CENTER)
        c.create_text(scx, sy1 - 8, text="SPEED", fill=GLASS_TEXT_DIM,
                      font=('Segoe UI', 8, 'bold'), anchor=tkinter.CENTER)

        # === Gear Display (center) ===
        gcx = w / 2
        self.gear_text = c.create_text(
            gcx, sy1 + gauge_size * 0.5, text="N", fill=GLASS_CYAN,
            font=('Segoe UI', max(24, int(gauge_size * 0.3)), 'bold'), anchor=tkinter.CENTER)
        c.create_text(gcx, sy1 - 8, text="GEAR", fill=GLASS_TEXT_DIM,
                      font=('Segoe UI', 8, 'bold'), anchor=tkinter.CENTER)

        # === RPM Gauge (right third) ===
        rx2 = w - 10
        rx1 = rx2 - gauge_size
        ry1, ry2 = sy1, sy1 + gauge_size
        self.rpm_arc_bg = c.create_arc(
            rx1, ry1, rx2, ry2, start=GAUGE_START_ANGLE, extent=GAUGE_FULL_EXTENT,
            style='arc', outline=GLASS_CARD_LIGHT, width=GAUGE_ARC_WIDTH)
        redline_extent = GAUGE_FULL_EXTENT * 0.15
        self.rpm_redline = c.create_arc(
            rx1, ry1, rx2, ry2,
            start=GAUGE_START_ANGLE - (GAUGE_FULL_EXTENT - redline_extent),
            extent=redline_extent,
            style='arc', outline="#331122", width=GAUGE_ARC_WIDTH + 2)
        # Gradient segments (10)
        self.rpm_segments = []
        self._rpm_prev_colors = [None] * 10
        for i in range(10):
            seg = c.create_arc(
                rx1, ry1, rx2, ry2,
                start=GAUGE_START_ANGLE + i * seg_extent, extent=seg_extent,
                style='arc', outline=GLASS_CYAN, width=GAUGE_ARC_WIDTH, state='hidden')
            self.rpm_segments.append(seg)
        rcx, rcy = (rx1 + rx2) / 2, (ry1 + ry2) / 2 + gauge_size * 0.06
        self.rpm_value_text = c.create_text(
            rcx, rcy - 5, text="0", fill=GLASS_CYAN,
            font=('Segoe UI', max(16, int(gauge_size * 0.17)), 'bold'), anchor=tkinter.CENTER)
        c.create_text(rcx, rcy + gauge_size * 0.12, text="rpm", fill=GLASS_TEXT_DIM,
                      font=('Segoe UI', 8), anchor=tkinter.CENTER)
        c.create_text(rcx, ry1 - 8, text="RPM", fill=GLASS_TEXT_DIM,
                      font=('Segoe UI', 8, 'bold'), anchor=tkinter.CENTER)

        # === Pedal bars (below gauges) ===
        bar_top = sy1 + gauge_size + 20
        bar_height = max(40, h - bar_top - 30)
        bar_width = max(20, int(w * 0.06))
        bar_gap = max(10, int(w * 0.04))
        accel_x = w / 2 - bar_gap - bar_width
        brake_x = w / 2 + bar_gap
        bar_bot = bar_top + bar_height

        c.create_text(accel_x + bar_width / 2, bar_top - 8, text="ACCEL",
                      fill=GLASS_TEXT_DIM, font=('Segoe UI', 7, 'bold'))
        self.accel_bar_bg = c.create_rectangle(
            accel_x, bar_top, accel_x + bar_width, bar_bot,
            fill=GLASS_CARD_LIGHT, outline=GLASS_BORDER)
        self.accel_bar_fill = c.create_rectangle(
            accel_x + 1, bar_bot, accel_x + bar_width - 1, bar_bot,
            fill=GLASS_GREEN, outline='')
        self.accel_bar_text = c.create_text(
            accel_x + bar_width / 2, bar_bot + 12, text="0%",
            fill=GLASS_GREEN, font=('Consolas', 9, 'bold'))

        c.create_text(brake_x + bar_width / 2, bar_top - 8, text="BRAKE",
                      fill=GLASS_TEXT_DIM, font=('Segoe UI', 7, 'bold'))
        self.brake_bar_bg = c.create_rectangle(
            brake_x, bar_top, brake_x + bar_width, bar_bot,
            fill=GLASS_CARD_LIGHT, outline=GLASS_BORDER)
        self.brake_bar_fill = c.create_rectangle(
            brake_x + 1, bar_bot, brake_x + bar_width - 1, bar_bot,
            fill=GLASS_RED, outline='')
        self.brake_bar_text = c.create_text(
            brake_x + bar_width / 2, bar_bot + 12, text="0%",
            fill=GLASS_RED, font=('Consolas', 9, 'bold'))

        self._pedal_geom = {
            'accel_x': accel_x, 'brake_x': brake_x,
            'bar_w': bar_width, 'bar_top': bar_top, 'bar_bot': bar_bot
        }

        # === Boost/Fuel bars (right of pedals) ===
        bf_x = brake_x + bar_width + max(15, int(w * 0.06))
        bf_w = max(60, int(w * 0.12))
        bf_h = 8

        # Boost bar
        c.create_text(bf_x + bf_w / 2, bar_top + 2, text="BOOST",
                      fill=GLASS_TEXT_DIM, font=('Segoe UI', 6, 'bold'))
        self.boost_bar_bg = c.create_rectangle(
            bf_x, bar_top + 12, bf_x + bf_w, bar_top + 12 + bf_h,
            fill=GLASS_CARD_LIGHT, outline=GLASS_BORDER)
        self.boost_bar_fill = c.create_rectangle(
            bf_x + 1, bar_top + 13, bf_x + 1, bar_top + 12 + bf_h - 1,
            fill=GLASS_ACCENT, outline='')
        self.boost_bar_text = c.create_text(
            bf_x + bf_w / 2, bar_top + 12 + bf_h + 8, text="0%",
            fill=GLASS_ACCENT, font=('Consolas', 7, 'bold'))

        # Fuel bar
        fuel_y = bar_top + 12 + bf_h + 20
        c.create_text(bf_x + bf_w / 2, fuel_y - 6, text="FUEL",
                      fill=GLASS_TEXT_DIM, font=('Segoe UI', 6, 'bold'))
        self.fuel_bar_bg = c.create_rectangle(
            bf_x, fuel_y + 4, bf_x + bf_w, fuel_y + 4 + bf_h,
            fill=GLASS_CARD_LIGHT, outline=GLASS_BORDER)
        self.fuel_bar_fill = c.create_rectangle(
            bf_x + 1, fuel_y + 5, bf_x + 1, fuel_y + 4 + bf_h - 1,
            fill=GLASS_GREEN, outline='')
        self.fuel_bar_text = c.create_text(
            bf_x + bf_w / 2, fuel_y + 4 + bf_h + 8, text="100%",
            fill=GLASS_GREEN, font=('Consolas', 7, 'bold'))

        self._bf_geom = {'x': bf_x, 'w': bf_w, 'h': bf_h}

    def _build_tires_gforce_right(self, parent):
        """Right sub-frame: Tire canvas (top) + G-force canvas (bottom).
        Canvas items are created on first <Configure> event."""
        parent.grid_rowconfigure(0, weight=3)
        parent.grid_rowconfigure(1, weight=2)
        parent.grid_columnconfigure(0, weight=1)

        # Tire canvas
        tire_frame = tkinter.Frame(parent, bg=GLASS_CARD)
        tire_frame.grid(row=0, column=0, sticky='news')

        self.tire_canvas = tkinter.Canvas(tire_frame, background=GLASS_CARD,
                                          bd=0, highlightthickness=False)
        self.tire_canvas.pack(fill='both', expand=True, padx=5, pady=5)
        self._tire_items_created = False
        self.tire_canvas.bind('<Configure>', self._on_tire_configure)

        # G-Force canvas
        gforce_frame = tkinter.Frame(parent, bg=GLASS_CARD)
        gforce_frame.grid(row=1, column=0, sticky='news')

        self.gforce_canvas = tkinter.Canvas(gforce_frame, bg=GLASS_CARD,
                                            bd=0, highlightthickness=False)
        self.gforce_canvas.pack(fill='both', expand=True, padx=5, pady=5)
        self._gforce_items_created = False
        self.gforce_canvas.bind('<Configure>', self._on_gforce_configure)

    def _on_tire_configure(self, event):
        """Create tire Canvas items once sized."""
        if self._tire_items_created:
            return
        self._tire_items_created = True
        tw, th = event.width, event.height
        if tw < 30 or th < 30:
            return
        c = self.tire_canvas
        self.tire_canvas_text = c.create_text(
            tw / 2, 12, text=self.tire_information_txt.get(), fill=GLASS_TEXT,
            font=('Segoe UI', 11, 'bold'), anchor=tkinter.CENTER)

        tire_w = tw * 0.38
        tire_h = th * 0.30
        gap_x = tw * 0.06
        gap_y = th * 0.08
        margin_x = (tw - tire_w * 2 - gap_x) / 2
        margin_y = 28
        tire_positions = {
            "FL": [margin_x, margin_y, margin_x + tire_w, margin_y + tire_h],
            "FR": [margin_x + tire_w + gap_x, margin_y, margin_x + tire_w * 2 + gap_x, margin_y + tire_h],
            "RL": [margin_x, margin_y + tire_h + gap_y, margin_x + tire_w, margin_y + tire_h * 2 + gap_y],
            "RR": [margin_x + tire_w + gap_x, margin_y + tire_h + gap_y,
                   margin_x + tire_w * 2 + gap_x, margin_y + tire_h * 2 + gap_y],
        }
        for pos, coords in tire_positions.items():
            self.tires[pos] = self.round_rectangle(
                c, *coords, radius=8,
                fill=GLASS_CARD, width=2, outline=GLASS_BORDER)
            cx = (coords[0] + coords[2]) / 2
            cy = (coords[1] + coords[3]) / 2
            # Slip text (upper center)
            self.tire_slip_text[pos] = c.create_text(
                cx, cy - tire_h * 0.12, text="0.00", fill=GLASS_TEXT,
                font=('Consolas', 9, 'bold'), anchor=tkinter.CENTER)
            # Temperature text (lower center)
            self.tire_temp_text[pos] = c.create_text(
                cx, cy + tire_h * 0.18, text="--", fill=GLASS_TEXT_DIM,
                font=('Consolas', 7), anchor=tkinter.CENTER)
            # Suspension travel bar (top of tire box)
            susp_y = coords[1] + 3
            susp_w = (coords[2] - coords[0]) - 4
            c.create_rectangle(coords[0] + 2, susp_y, coords[0] + 2 + susp_w, susp_y + 3,
                               fill=GLASS_CARD_LIGHT, outline='')
            self.tire_susp_bar[pos] = c.create_rectangle(
                coords[0] + 2, susp_y, coords[0] + 2, susp_y + 3,
                fill=GLASS_GREEN, outline='')

    def _on_gforce_configure(self, event):
        """Create G-force Canvas items once sized."""
        if self._gforce_items_created:
            return
        self._gforce_items_created = True
        gw, gh = event.width, event.height
        if gw < 30 or gh < 30:
            return
        c = self.gforce_canvas
        self._gforce_cx = gw / 2
        self._gforce_cy = gh / 2
        self._gforce_scale = (min(gw, gh) - 30) / 5  # extra padding to prevent overflow
        self._gforce_w = gw
        self._gforce_h = gh

        # Concentric circles
        for g in [0.5, 1.0, 1.5, 2.0]:
            r = g * self._gforce_scale
            c.create_oval(
                self._gforce_cx - r, self._gforce_cy - r,
                self._gforce_cx + r, self._gforce_cy + r,
                outline=GLASS_BORDER if g == 1.0 else GLASS_CARD_LIGHT, width=1)

        # Crosshairs
        c.create_line(
            self._gforce_cx - 2 * self._gforce_scale, self._gforce_cy,
            self._gforce_cx + 2 * self._gforce_scale, self._gforce_cy,
            fill=GLASS_CARD_LIGHT)
        c.create_line(
            self._gforce_cx, self._gforce_cy - 2 * self._gforce_scale,
            self._gforce_cx, self._gforce_cy + 2 * self._gforce_scale,
            fill=GLASS_CARD_LIGHT)

        # Labels - keep within canvas bounds
        label_pad = 14
        c.create_text(self._gforce_cx, label_pad, text="BRAKE", fill=GLASS_TEXT_DIM, font=('Segoe UI', 6))
        c.create_text(self._gforce_cx, gh - 6, text="ACCEL", fill=GLASS_TEXT_DIM, font=('Segoe UI', 6))
        c.create_text(label_pad, self._gforce_cy, text="LEFT", fill=GLASS_TEXT_DIM, font=('Segoe UI', 6))
        c.create_text(gw - label_pad, self._gforce_cy, text="RIGHT", fill=GLASS_TEXT_DIM, font=('Segoe UI', 6))

        # Trail + dot
        self.gforce_trail_line = c.create_line(0, 0, 0, 0, fill=GLASS_ACCENT, width=1.5, smooth=True)
        self.gforce_dot = c.create_oval(
            self._gforce_cx - 4, self._gforce_cy - 4,
            self._gforce_cx + 4, self._gforce_cy + 4,
            fill=GLASS_GREEN, outline='')
        self.gforce_text = c.create_text(
            gw - 8, 12, text="0.00G", fill=GLASS_GREEN,
            font=('Consolas', 8, 'bold'), anchor=tkinter.NE)

    # ---- Real-time gauge update methods ----

    @staticmethod
    def _lerp_color(c1, c2, t):
        """Linearly interpolate between two hex colors. Returns hex string."""
        r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
        r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _tire_temp_color(temp):
        """Continuous tire temperature to color per design spec.
        Scale: 50°→#3264dc, 75°→#00c864, 95°→#dcc800, 120°→#f03c28"""
        stops = [(50, 0x32, 0x64, 0xdc), (75, 0x00, 0xc8, 0x64),
                 (95, 0xdc, 0xc8, 0x00), (120, 0xf0, 0x3c, 0x28)]
        if temp <= stops[0][0]:
            return f"#{stops[0][1]:02x}{stops[0][2]:02x}{stops[0][3]:02x}"
        if temp >= stops[-1][0]:
            return f"#{stops[-1][1]:02x}{stops[-1][2]:02x}{stops[-1][3]:02x}"
        for i in range(len(stops) - 1):
            t1, r1, g1, b1 = stops[i]
            t2, r2, g2, b2 = stops[i + 1]
            if t1 <= temp <= t2:
                f = (temp - t1) / (t2 - t1)
                return f"#{int(r1+(r2-r1)*f):02x}{int(g1+(g2-g1)*f):02x}{int(b1+(b2-b1)*f):02x}"
        return "#3264dc"

    def _update_speed_gauge(self, speed):
        """Update speed arc gauge with gradient segments."""
        if not hasattr(self, 'speed_segments'):
            return
        max_speed = 400
        pct = min(speed / max_speed, 1.0)
        n_active = int(pct * 10)
        color = GLASS_GREEN
        for i in range(10):
            if i < n_active:
                # Gradient: green -> yellow -> red
                seg_pct = (i + 0.5) / 10
                if seg_pct < 0.5:
                    c = self._lerp_color(GLASS_GREEN, GLASS_YELLOW, seg_pct / 0.5)
                else:
                    c = self._lerp_color(GLASS_YELLOW, GLASS_RED, (seg_pct - 0.5) / 0.5)
                color = c
                if self._speed_prev_colors[i] != c:
                    self.gauge_canvas.itemconfig(self.speed_segments[i], outline=c, state='normal')
                    self._speed_prev_colors[i] = c
            else:
                if self._speed_prev_colors[i] is not None:
                    self.gauge_canvas.itemconfig(self.speed_segments[i], state='hidden')
                    self._speed_prev_colors[i] = None
        self.gauge_canvas.itemconfig(self.speed_value_text, text=str(int(speed)), fill=color)

    def _update_rpm_gauge(self, rpm, max_rpm):
        """Update RPM arc gauge with gradient segments."""
        if not hasattr(self, 'rpm_segments'):
            return
        max_rpm = max(max_rpm, 5000)
        pct = min(rpm / max_rpm, 1.0)
        n_active = int(pct * 10)
        color = GLASS_CYAN
        for i in range(10):
            if i < n_active:
                seg_pct = (i + 0.5) / 10
                if seg_pct < 0.85:
                    c = self._lerp_color(GLASS_CYAN, GLASS_ACCENT, seg_pct / 0.85)
                else:
                    c = self._lerp_color(GLASS_ACCENT, GLASS_RED, (seg_pct - 0.85) / 0.15)
                color = c
                if self._rpm_prev_colors[i] != c:
                    self.gauge_canvas.itemconfig(self.rpm_segments[i], outline=c, state='normal')
                    self._rpm_prev_colors[i] = c
            else:
                if self._rpm_prev_colors[i] is not None:
                    self.gauge_canvas.itemconfig(self.rpm_segments[i], state='hidden')
                    self._rpm_prev_colors[i] = None
        self.gauge_canvas.itemconfig(self.rpm_value_text, text=str(int(rpm)), fill=color)

    def _update_gear_display(self, gear):
        """Update gear number display with flash glow on change."""
        if not hasattr(self, 'gear_text'):
            return
        text = "N" if gear == 0 else str(gear)
        if gear != self._last_gear and self._last_gear != 0:
            self.gauge_canvas.itemconfig(self.gear_text, text=text, fill="#ffffff")
            if getattr(self, '_gear_flash_id', None) is not None:
                try:
                    self.root.after_cancel(self._gear_flash_id)
                except ValueError:
                    pass
            self._gear_flash_id = self.root.after(150,
                lambda: self.gauge_canvas.itemconfig(self.gear_text, fill=GLASS_CYAN)
                if self.root.winfo_exists() and hasattr(self, 'gear_text') else None)
        else:
            self.gauge_canvas.itemconfig(self.gear_text, text=text, fill=GLASS_CYAN)
        self._last_gear = gear

    def _update_pedal_bars(self, accel, brake):
        """Update accel/brake pedal bar fills."""
        if not hasattr(self, 'accel_bar_fill'):
            return
        g = self._pedal_geom
        bar_range = g['bar_bot'] - g['bar_top']

        # Accel
        accel_pct = accel / constants.FORZA_INPUT_MAX
        accel_h = accel_pct * bar_range
        self.gauge_canvas.coords(self.accel_bar_fill,
                                 g['accel_x'] + 1, g['bar_bot'] - accel_h,
                                 g['accel_x'] + g['bar_w'] - 1, g['bar_bot'])
        self.gauge_canvas.itemconfig(self.accel_bar_text,
                                     text=f"{accel_pct * 100:.1f}%")

        # Brake
        brake_pct = brake / constants.FORZA_INPUT_MAX
        brake_h = brake_pct * bar_range
        self.gauge_canvas.coords(self.brake_bar_fill,
                                 g['brake_x'] + 1, g['bar_bot'] - brake_h,
                                 g['brake_x'] + g['bar_w'] - 1, g['bar_bot'])
        self.gauge_canvas.itemconfig(self.brake_bar_text,
                                     text=f"{brake_pct * 100:.1f}%")

    def _update_boost_fuel(self, boost, fuel):
        """Update Boost/Fuel horizontal bars. Both 0.0-1.0 normalized."""
        if not hasattr(self, 'boost_bar_fill'):
            return
        g = self._bf_geom
        # Boost
        boost_pct = max(0.0, min(1.0, boost))
        boost_fill_w = boost_pct * (g['w'] - 2)
        boost_y1 = self.gauge_canvas.coords(self.boost_bar_bg)[1] + 1
        boost_y2 = boost_y1 + g['h'] - 2
        self.gauge_canvas.coords(self.boost_bar_fill, g['x'] + 1, boost_y1,
                                 g['x'] + 1 + boost_fill_w, boost_y2)
        self.gauge_canvas.itemconfig(self.boost_bar_text, text=f"{boost_pct * 100:.0f}%")

        # Fuel
        fuel_pct = max(0.0, min(1.0, fuel))
        fuel_fill_w = fuel_pct * (g['w'] - 2)
        fuel_y1 = self.gauge_canvas.coords(self.fuel_bar_bg)[1] + 1
        fuel_y2 = fuel_y1 + g['h'] - 2
        self.gauge_canvas.coords(self.fuel_bar_fill, g['x'] + 1, fuel_y1,
                                 g['x'] + 1 + fuel_fill_w, fuel_y2)
        fuel_color = GLASS_RED if fuel_pct < 0.15 else (GLASS_YELLOW if fuel_pct < 0.3 else GLASS_GREEN)
        self.gauge_canvas.itemconfig(self.fuel_bar_fill, fill=fuel_color)
        self.gauge_canvas.itemconfig(self.fuel_bar_text, text=f"{fuel_pct * 100:.0f}%", fill=fuel_color)

    def _update_live_torque(self, data):
        """Update live torque chart cursor with current operating point."""
        if not hasattr(self, 'live_torque_chart'):
            return
        gear = data['gear']
        ratio = self.engine.gear_ratios.get(gear, {}).get('ratio', None)
        output_torque = data['torque'] / ratio if ratio and ratio > 0 else None
        self.live_torque_chart.update_live_cursor(data['rpm'], output_torque, gear)

    def _update_rpm_speed_timeline(self, data):
        """Update RPM/Speed scrolling timeline."""
        if hasattr(self, 'rpm_speed_chart'):
            self.rpm_speed_chart.push([data['rpm'], data['speed']])

    def _update_gforce_trace(self, data):
        """Update G-Force scrolling timeline (different from 2D gforce diagram)."""
        if hasattr(self, 'gforce_trace_chart'):
            self.gforce_trace_chart.push([data['accel_x'], data['accel_z']])

    def _update_coach_hud(self, data):
        if not self.coach_mode or self.coach_hud is None:
            return
        self.coach_hud.update(
            driving_line=data.get('norm_driving_line', 0),
            ai_brake_diff=data.get('norm_ai_brake_diff', 0),
            tire_slips=data.get('slips', {}),
        )

    def _update_gforce(self, accel_x, accel_z):
        """Update G-force diagram. lateral=accel_x, longitudinal=accel_z."""
        if not hasattr(self, 'gforce_dot'):
            return
        cx, cy = self._gforce_cx, self._gforce_cy
        scale = self._gforce_scale

        # Screen coordinates: x right=positive, y down=positive
        # Forza: accel_x positive=right, accel_z positive=forward (screen up = brake)
        px = cx + accel_x * scale
        py = cy - accel_z * scale  # invert: forward acceleration = screen up = toward BRAKE label

        # Clamp to actual canvas bounds
        px = max(5, min(px, self._gforce_w - 5))
        py = max(5, min(py, self._gforce_h - 5))

        # Update trail
        self.gforce_trail.append((px, py))
        if len(self.gforce_trail) >= 2:
            coords = []
            for tx, ty in self.gforce_trail:
                coords.extend([tx, ty])
            self.gforce_canvas.coords(self.gforce_trail_line, *coords)

        # Update dot
        self.gforce_canvas.coords(self.gforce_dot, px - 4, py - 4, px + 4, py + 4)

        # Color by magnitude
        g_mag = math.sqrt(accel_x ** 2 + accel_z ** 2)
        if g_mag < 1.0:
            color = GLASS_GREEN
        elif g_mag < 1.5:
            color = GLASS_YELLOW
        else:
            color = GLASS_RED
        self.gforce_canvas.itemconfig(self.gforce_dot, fill=color)
        self.gforce_canvas.itemconfig(self.gforce_text, text=f"{g_mag:.2f}G", fill=color)

    # ---- Shift point panel (right column, row 0) ----

    def set_shift_point_frame(self, parent):
        """Create flat shift point table matching design spec (Gear | km/h | RPM)."""
        table = tkinter.Frame(parent, bg=GLASS_CARD)
        table.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        for col in range(3):
            table.grid_columnconfigure(col, weight=1)

        # Header row (i18n-aware)
        self._shift_headers = []
        header_texts = [self.shift_point_txt.get(), self.speed_txt.get(), self.rpm_txt.get()]
        for col, txt in enumerate(header_texts):
            lbl = tkinter.Label(table, text=txt, bg=GLASS_CARD, fg=GLASS_TEXT_DIM,
                                font=('Segoe UI', 8, 'bold'), anchor='center')
            lbl.grid(row=0, column=col, sticky='ew', padx=2, pady=(2, 1))
            self._shift_headers.append(lbl)

        # Separator
        sep = tkinter.Frame(table, bg=GLASS_BORDER, height=1)
        sep.grid(row=1, column=0, columnspan=3, sticky='ew', padx=2, pady=1)

        # Data rows
        self.speed_tree = {}
        self.rpm_tree = {}
        for i in range(1, 11):
            row = i + 1
            gear_lbl = tkinter.Label(table, text=str(i), bg=GLASS_CARD, fg=GLASS_TEXT_DIM,
                                      font=('Consolas', 9), anchor='center')
            gear_lbl.grid(row=row, column=0, sticky='ew', padx=2)

            speed_lbl = tkinter.Label(table, text='-', bg=GLASS_CARD, fg=GLASS_TEXT,
                                       font=('Consolas', 9), anchor='center')
            speed_lbl.grid(row=row, column=1, sticky='ew', padx=2)
            self.speed_tree[i] = speed_lbl

            rpm_lbl = tkinter.Label(table, text='-', bg=GLASS_CARD, fg=GLASS_TEXT,
                                     font=('Consolas', 9), anchor='center')
            rpm_lbl.grid(row=row, column=2, sticky='ew', padx=2)
            self.rpm_tree[i] = rpm_lbl

    # ---- Button panel (left column, row 1) ----

    def set_button_frame(self):
        # No card wrapper — raw buttons matching mockup style
        self.button_frame = tkinter.Frame(self.root, bg=GLASS_BG, borderwidth=0)
        self.button_frame.grid(row=1, column=0, sticky='news')

        buttons = [
            (self.collect_button_txt, self.collect_data_handler, GLASS_ACCENT, "white"),
            (self.analysis_button_txt, self.analysis_handler, GLASS_ACCENT2, "white"),
            (self.run_button_txt, self.run_handler, GLASS_GREEN, "#0f0c29"),
            (self.playback_button_txt, self.playback_handler, GLASS_CYAN, "#0f0c29"),
            (self.pause_button_txt, self.pause_handler, "#ff9500", "white"),
            (self.exit_button_txt, self.exit_handler, "#666688", "white"),
        ]

        for i, (name, func, color, fg_color) in enumerate(buttons):
            btn = tkinter.Button(self.button_frame, textvariable=name,
                                 bg=color, fg=fg_color, activebackground=color,
                                 activeforeground=fg_color, borderwidth=0,
                                 font=('Segoe UI', 10, 'bold'), relief="flat", bd=0)
            btn.bind('<Button-1>', func)
            btn.place(relx=0.5, rely=1 / (len(buttons) + 1) * (i + 0.5),
                      relwidth=0.85, relheight=1 / (len(buttons) + 1) * 0.88, anchor='center')

        # Record checkbox (bottom of button frame)
        self.record_var = tkinter.BooleanVar(value=False)
        record_cb = tkinter.Checkbutton(self.button_frame, textvariable=self.record_button_txt,
                                        variable=self.record_var, bg=GLASS_BG, fg=GLASS_TEXT,
                                        selectcolor=GLASS_CARD_LIGHT, activebackground=GLASS_BG,
                                        activeforeground=GLASS_CYAN, font=('Segoe UI', 9),
                                        borderwidth=0, relief="flat")
        record_cb.place(relx=0.5, rely=1 / (len(buttons) + 1) * (len(buttons) + 0.5),
                        anchor='center')

    # ---- Bottom area: Log + Live Dashboard (center column, row 1) ----

    def set_bottom_area(self):
        """Create Log panel + Live Dashboard in center column, row 1."""
        bottom = tkinter.Frame(self.root, bg=GLASS_BG)
        bottom.grid(row=1, column=1, sticky='news')
        bottom.grid_columnconfigure(0, weight=2)   # Log (2fr)
        bottom.grid_columnconfigure(1, weight=3)   # Live Dashboard (3fr)
        bottom.grid_rowconfigure(0, weight=1)

        # --- Left: Log panel ---
        log_frame = self._glass_frame(bottom)
        log_frame.grid(row=0, column=0, sticky='news', padx=(0, 3))
        self.log_card_title = self._glass_label(log_frame,
            text=self.log_tab_txt.get(), fg=GLASS_TEXT_DIM,
            font=('Segoe UI', 9))
        self.log_card_title.pack(anchor='w', padx=8, pady=(6, 2))

        log = scrolledtext.ScrolledText(log_frame, bg=GLASS_LOG_BG, borderwidth=0,
                                        font='Consolas 9', fg=GLASS_LOG_FG,
                                        insertbackground=GLASS_LOG_FG)
        log.pack(fill="both", expand=True, pady=(4, 0))
        log_handler = TextHandler(log)
        self.logger = (Logger(log_handler))(constants.LOGGER_NAME)

        btn = tkinter.Button(log_frame, textvariable=self.clear_log_text,
                             bg=GLASS_CARD_LIGHT, fg=GLASS_TEXT, borderwidth=0,
                             activebackground=GLASS_CARD, activeforeground=GLASS_CYAN,
                             font=('Segoe UI', 8))
        btn.bind('<Button-1>', lambda x: log.delete(1.0, 'end'))
        btn.place(relx=0.93, rely=0.053, relwidth=0.05, relheight=0.07,
                  anchor='center', bordermode='inside')

        # --- Right: Live Dashboard ---
        live_frame = self._glass_frame(bottom)
        live_frame.grid(row=0, column=1, sticky='news', padx=(3, 0))
        live_frame.grid_rowconfigure(0, weight=0)  # title
        live_frame.grid_rowconfigure(1, weight=1)  # Torque card
        live_frame.grid_rowconfigure(2, weight=1)  # RPM/Speed card
        live_frame.grid_rowconfigure(3, weight=1)  # G-Force card
        live_frame.grid_columnconfigure(0, weight=1)

        self.live_card_title = self._glass_label(live_frame,
            text=self.live_torque_tab_txt.get(), fg=GLASS_GREEN,
            font=('Segoe UI', 9, 'bold'))
        self.live_card_title.grid(row=0, column=0, sticky='w', padx=8, pady=(6, 2))

        # Card 1: Torque (reuse LiveTorqueChart)
        card1 = self._live_card(live_frame, 1)
        torque_canvas = tkinter.Canvas(card1, bg='#0d0d1a', highlightthickness=0)
        torque_canvas.pack(fill="both", expand=True)
        self.live_torque_chart = LiveTorqueChart(torque_canvas, self.language)

        # Card 2: RPM / Speed timeline
        card2 = self._live_card(live_frame, 2)
        rpm_canvas = tkinter.Canvas(card2, bg='#0d0d1a', highlightthickness=0)
        rpm_canvas.pack(fill="both", expand=True)
        self.rpm_speed_chart = LiveTimelineChart(rpm_canvas, [
            {'name': 'RPM', 'color': '#00d4ff', 'max_val': 9000},
            {'name': 'Speed', 'color': '#00ff88', 'max_val': 400},
        ])

        # Card 3: G-Force trace timeline
        card3 = self._live_card(live_frame, 3)
        gf_canvas = tkinter.Canvas(card3, bg='#0d0d1a', highlightthickness=0)
        gf_canvas.pack(fill="both", expand=True)
        self.gforce_trace_chart = LiveTimelineChart(gf_canvas, [
            {'name': 'Lateral', 'color': '#667eea', 'max_val': 2.0},
            {'name': 'Longitudinal', 'color': '#ff9500', 'max_val': 2.0},
        ])

    def _live_card(self, parent, row):
        """Create a glass card frame inside the Live Dashboard."""
        card = self._glass_frame(parent)
        card.grid(row=row, column=0, sticky='news', pady=1)
        return card

    # ---- Right column: Shift Points + Charts + Info ----

    def set_right_frame(self):
        """Create right column with Shift Points, Charts, and Info."""
        right = tkinter.Frame(self.root, bg=GLASS_BG)
        right.grid(row=0, column=2, rowspan=2, sticky='news', padx=(4, 0))
        right.grid_rowconfigure(0, weight=0)   # Shift Points (auto)
        right.grid_rowconfigure(1, weight=1)   # Charts (expand)
        right.grid_rowconfigure(2, weight=0)   # Info (auto)
        right.grid_columnconfigure(0, weight=1)

        # --- Top: Shift Points ---
        shift_frame = self._glass_frame(right)
        shift_frame.grid(row=0, column=0, sticky='new', pady=(0, 2))
        self.shift_card_title = self._glass_label(shift_frame,
            text=self.shift_point_tab_txt.get(), fg=GLASS_TEXT_DIM,
            font=('Segoe UI', 9))
        self.shift_card_title.pack(anchor='w', padx=8, pady=(6, 2))
        self.set_shift_point_frame(shift_frame)

        # --- Middle: Charts (matplotlib) ---
        charts_frame = self._glass_frame(right)
        charts_frame.grid(row=1, column=0, sticky='news', pady=2)
        self.charts_card_title = self._glass_label(charts_frame,
            text=self.charts_tab_txt.get(), fg=GLASS_TEXT_DIM,
            font=('Segoe UI', 9))
        self.charts_card_title.pack(anchor='w', padx=8, pady=(6, 2))
        self.chart_figure = Figure(figsize=(4, 4), dpi=80, facecolor=GLASS_BG)
        self.chart_axes = self.chart_figure.subplots(2, 1, squeeze=False)
        self._style_chart_axes()
        self.chart_figure.tight_layout(pad=1.0)
        chart_canvas = FigureCanvasTkAgg(self.chart_figure, master=charts_frame)
        chart_canvas.get_tk_widget().pack(fill="both", expand=True)
        self.chart_canvas_widget = chart_canvas

        # --- Bottom: Info ---
        info_frame = self._glass_frame(right)
        info_frame.grid(row=2, column=0, sticky='sew', pady=(2, 0))
        self._glass_label(info_frame, text='INFO', fg=GLASS_TEXT_DIM,
                          font=('Segoe UI', 9)).pack(anchor='w', padx=8, pady=(6, 2))
        self.program_info = tkinter.Label(info_frame,
            text=constants.PROGRAM_INFO_TXT[self.language],
            bg=GLASS_CARD, fg=GLASS_TEXT_DIM, justify='left',
            font=('Consolas', 8), anchor='w')
        self.program_info.pack(fill='x', padx=5, pady=(0, 4))

    # ---- Chart rendering ----

    def _render_charts(self):
        """Render performance charts in the embedded figure."""
        if self.chart_figure is None or len(self.engine.gear_ratios) == 0:
            return

        try:
            self.chart_figure.clear()
            self.chart_axes = self.chart_figure.subplots(2, 1, squeeze=False)

            helper.plot_torque_speed(self.engine, self.chart_axes, 0, 0)
            helper.plot_torque_rpm(self.engine, self.chart_axes, 1, 0)

            self._style_chart_axes()
            self.chart_figure.tight_layout(pad=1.5)
            self.chart_canvas_widget.draw()
        except Exception as e:
            self.logger.warning(f'Chart rendering failed: {e}')

    def _style_chart_axes(self):
        """Apply glass theme to all chart axes."""
        for ax_row in self.chart_axes:
            for ax in ax_row:
                ax.set_facecolor(GLASS_CHART_FACE)
                ax.tick_params(colors=GLASS_TEXT_DIM, labelsize=7)
                ax.xaxis.label.set_color(GLASS_TEXT)
                ax.yaxis.label.set_color(GLASS_TEXT)
                ax.title.set_color(GLASS_CYAN)
                ax.title.set_fontsize(9)
                for spine in ax.spines.values():
                    spine.set_color(GLASS_BORDER)
                legend = ax.get_legend()
                if legend:
                    legend.get_frame().set_facecolor(GLASS_CHART_FACE)
                    legend.get_frame().set_edgecolor(GLASS_BORDER)
                    for text in legend.get_texts():
                        text.set_color(GLASS_TEXT)

    # ---- Button handlers ----

    def collect_data_handler(self, event):
        if self.engine.isRunning:
            self.logger.info('stopping gear test')

            def stopping():
                self.engine.isRunning = False
                self._save_recorder()
                self.reset_car_info()

            self.threadPool.submit(stopping)
        else:
            self.logger.info('starting gear test')

            def starting():
                self.engine.isRunning = True
                self.engine.test_gear(self.update_car_info)

            self.threadPool.submit(starting)

    def analysis_handler(self, event, performance_profile=True, is_guid=True):
        if len(self.engine.records) <= 0:
            self.logger.info(f'load config {constants.EXAMPLE_CAR_ORDINAL}.json for analysis as an example')
            helper.load_config(self.engine, os.path.join(constants.ROOT_PATH, constants.EXAMPLE_DIR_NAME,
                                                          f'{constants.EXAMPLE_CAR_ORDINAL}.json'))
        self.logger.info('Analysis')
        self.engine.analyze(performance_profile=False, is_gui=is_guid)
        self.update_tree()
        self._render_charts()
        self.live_torque_chart.update_from_analysis(self.engine)

    def run_handler(self, event):
        if self.engine.isRunning:
            self.engine.logger.info('stopping auto gear')

            def stopping():
                self.engine.isRunning = False
                self._save_recorder()
                self.reset_car_info()

            self.threadPool.submit(stopping)
        else:
            self.engine.logger.info('starting auto gear')

            # Setup recorder if checkbox is checked
            if self.record_var.get():
                recording_dir = os.path.join(constants.ROOT_PATH, constants.RECORDING_DIR_NAME)
                self.engine.recorder = Recorder(output_dir=recording_dir)
                self.engine.logger.info('[Record] recording enabled')

            # Set isRunning on GUI thread to prevent race condition
            self.engine.isRunning = True
            self.threadPool.submit(self.engine.run, self.update_tree, self.update_car_info)

    def playback_handler(self, event):
        if self.engine.isRunning:
            self.engine.logger.info('stopping playback')
            self.engine.isRunning = False
            return

        from tkinter import filedialog
        filepath = filedialog.askopenfilename(
            title='Select Recording',
            filetypes=[('Forza Recording', '*.f6rec.json'), ('All Files', '*.*')],
            initialdir=os.path.join(constants.ROOT_PATH, constants.RECORDING_DIR_NAME)
        )
        if not filepath:
            return

        try:
            meta = PlaybackSource.load_metadata(filepath)
            self.logger.info(f'[Playback] {meta["packet_count"]} packets, {meta["duration_sec"]:.1f}s')
        except Exception as e:
            self.logger.error(f'[Playback] failed to load: {e}')
            return

        # Set isRunning on GUI thread to prevent race condition
        self.engine.isRunning = True
        self.threadPool.submit(self.engine.run_playback, filepath, self.update_tree, self.update_car_info)

    def _save_recorder(self):
        """Save recorder data if active. Called from worker thread."""
        if self.engine.recorder is not None:
            try:
                path = self.engine.recorder.save(metadata={
                    'format': self.engine.packet_format,
                    'car_ordinal': self.engine.ordinal,
                })
                self.engine.logger.info(f'[Record] saved: {path} ({self.engine.recorder.packet_count} packets)')
            except ValueError as e:
                self.engine.logger.warning(f'[Record] save skipped: {e}')
            finally:
                self.engine.recorder = None

    def pause_handler(self, event):
        self._save_recorder()
        self.engine.isRunning = False
        if hasattr(self.engine, 'server_socket'):
            helper.close_socket(self.engine)
        self.listener.stop()
        self.threadPool.shutdown(wait=False)
        self.reset_car_info()
        self.threadPool = ThreadPoolExecutor(max_workers=constants.MAX_WORKER_THREADS, thread_name_prefix=constants.THREAD_NAME_PREFIX)
        self.engine.threadPool = self.threadPool
        self.listener = Listener(on_press=self.on_press)
        self.listener.start()
        self.engine.logger.info('stopped')

    def exit_handler(self, event):
        self.engine.isRunning = False
        if hasattr(self.engine, 'server_socket'):
            helper.close_socket(self.engine)
        helper.dump_settings(self.engine)
        self.engine.logger.info('bye~')
        self.listener.stop()
        self.root.destroy()
        self.threadPool.shutdown(wait=False)

    # ---- Utility ----

    def round_rectangle(self, canvas, x1, y1, x2, y2, radius=25, **kwargs):
        points = [
            x1 + radius, y1, x1 + radius, y1, x2 - radius, y1, x2 - radius, y1,
            x2, y1, x2, y1 + radius, x2, y1 + radius, x2, y2 - radius, x2, y2 - radius,
            x2, y2, x2 - radius, y2, x2 - radius, y2, x1 + radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y2 - radius, x1, y1 + radius, x1, y1 + radius,
            x1, y1
        ]
        return canvas.create_polygon(points, **kwargs, smooth=True)


def main():
    GlassWindow()


if __name__ == "__main__":
    main()
