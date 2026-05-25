"""Pywebview GUI for Horizon6AutoGear — glassmorphism web frontend.

Replaces gui_glass.py with a pywebview-based UI that renders the HTML mockup.
Python backend owns the Forza engine and pushes telemetry via evaluate_js().
"""

import json
import logging
import os
import sys
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor

# macOS keyboard listener workaround:
# pynput.keyboard.Listener calls TSMGetInputSourceProperty from background thread
# via ctypes, which violates macOS GCD queue requirements and causes SIGTRAP.
# Solution: Use macOS-native CGEventTap on main thread RunLoop.
if sys.platform == 'darwin':
    from horizon6_autogear.shifting.keyboard_macos import macOSKeyboardListener as KeyboardListener
else:
    from pynput.keyboard import Listener as KeyboardListener

import webview  # noqa: E402

import horizon6_autogear.config.config as constants
import horizon6_autogear.utils.helper as helper
import horizon6_autogear.shifting.keyboard as keyboard_helper
from horizon6_autogear.core.forza import Forza
from horizon6_autogear.core.recorder import Recorder
from horizon6_autogear.core.playback import PlaybackSource
from horizon6_autogear.utils.logger import Logger

warnings.filterwarnings("ignore", category=UserWarning)


def _resource_path(relative):
    """Resolve path relative to project root — works in dev and PyInstaller bundle."""
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        relative)


HTML_FILE = _resource_path(os.path.join("web", "index.html"))
THEMES_DIR = _resource_path(os.path.join("web", "themes"))
API_JS = _resource_path(os.path.join("web", "api.js"))

THEMES = {
    'phantom': ('Phantom', 'phantom.html'),
}


def _load_theme_html(theme_name):
    """Load theme HTML and inject api.js inline (avoids macOS WebKit local file restrictions)."""
    entry = THEMES.get(theme_name)
    if not entry:
        with open(HTML_FILE) as f:
            return f.read()
    theme_path = os.path.join(THEMES_DIR, entry[1])
    if not os.path.exists(theme_path):
        with open(HTML_FILE, encoding='utf-8') as f:
            return f.read()
    with open(theme_path, encoding='utf-8') as f:
        html = f.read()
    if '../api.js' in html and os.path.exists(API_JS):
        with open(API_JS, encoding='utf-8') as f:
            api_js = f.read()
        html = html.replace('<script src="../api.js"></script>',
                            f'<script>\n{api_js}\n</script>')
    return html


class WebLogHandler(logging.Handler):
    """Pushes log records to the web frontend via evaluate_js."""

    def __init__(self, api):
        logging.Handler.__init__(self)
        self._api = api

    def emit(self, record):
        msg = self.format(record)
        self._api._js_call(f"appendLog({json.dumps(msg)})")


class Api:
    """Backend API exposed to JavaScript via pywebview."""

    def __init__(self):
        self._window = None
        self._js_lock = threading.Lock()
        self._listener_lock = threading.Lock()
        self._closing = False
        self._auto_live = False
        self.engine = None
        self.threadPool = None
        self.listener = None
        self._listener_start_requested = False
        self.logger = None
        self.language = helper.get_sys_lang()
        self._record_enabled = False
        self._app_state = "idle"

    def set_window(self, window):
        self._window = window

    def _js_call(self, js_code):
        if self._closing:
            return
        with self._js_lock:
            if self._closing:
                return
            try:
                self._window.evaluate_js(js_code)
            except Exception:
                pass

    # ---- Init (called from JS after page load) ----

    def init_app(self):
        """Called by JS after DOM is ready. Initializes engine on first call,
        re-pushes state on subsequent calls (e.g. after theme switch)."""
        if self.engine is not None:
            # Theme switch: just push current state to new DOM
            self._push_settings()
            self._push_i18n()
            return

        self.threadPool = ThreadPoolExecutor(
            max_workers=constants.MAX_WORKER_THREADS,
            thread_name_prefix=constants.THREAD_NAME_PREFIX)
        log_handler = WebLogHandler(self)
        log_handler.setLevel(logging.INFO)
        logger = Logger(custom_handler=log_handler)(constants.LOGGER_NAME)
        self.engine = Forza(self.threadPool, logger, constants.PACKET_FORMAT,
                            enable_clutch=constants.ENABLE_CLUTCH)
        self.logger = logger

        self.logger.info('Forza Horizon 5: Auto Gear Shifting Started - Web Edition!')
        self._push_settings()

        # Start keyboard listener for shortcuts
        self.start_listener()

        # Auto-start live telemetry on launch
        self._auto_live = True
        self.run()

    # ---- Button handlers ----

    def collect(self):
        if self.engine.isRunning:
            self.logger.info('stopping gear test')

            def stopping():
                self.engine.isRunning = False
                self._save_recorder()
                self._reset_dashboard()

            self.threadPool.submit(stopping)
        else:
            self.logger.info('starting gear test')

            def starting():
                self.engine.isRunning = True
                self.engine.test_gear(self.update_car_info)

            self.threadPool.submit(starting)

    def analyze(self):
        if len(self.engine.records) <= 0:
            self.logger.info(
                f'load config {constants.EXAMPLE_CAR_ORDINAL}.json for analysis as an example')
            helper.load_config(
                self.engine,
                os.path.join(constants.ROOT_PATH, constants.EXAMPLE_DIR_NAME,
                             f'{constants.EXAMPLE_CAR_ORDINAL}.json'))
        self.logger.info('Analysis')
        self.engine.analyze(performance_profile=False, is_gui=True)
        self.update_tree()
        self._render_charts()
        self._push_live_torque_data()

    def run(self):
        if self.engine.isRunning:
            self.engine.logger.info('stopping auto gear')

            def stopping():
                self.engine.isRunning = False
                self._save_recorder()
                self._reset_dashboard()

            self.threadPool.submit(stopping)
        else:
            self.engine.logger.info('starting auto gear')
            if self._record_enabled:
                recording_dir = os.path.join(constants.ROOT_PATH, constants.RECORDING_DIR_NAME)
                self.engine.recorder = Recorder(output_dir=recording_dir)
                self.engine.logger.info('[Record] recording enabled')

            self.engine.isRunning = True
            self.threadPool.submit(
                self.engine.run, self.update_tree, self.update_car_info)

    def pause(self):
        if not self.engine:
            return
        self._auto_live = False
        self._save_recorder()
        self.engine.isRunning = False
        if hasattr(self.engine, 'server_socket'):
            helper.close_socket(self.engine)
        self._stop_listener()
        self.threadPool.shutdown(wait=False)
        self._reset_dashboard()
        self.threadPool = ThreadPoolExecutor(
            max_workers=constants.MAX_WORKER_THREADS,
            thread_name_prefix=constants.THREAD_NAME_PREFIX)
        self.engine.threadPool = self.threadPool
        # Start keyboard listener for shortcuts
        self.start_listener()
        self.engine.logger.info('stopped')

    def exit(self):
        self._closing = True
        if not self.engine:
            threading.Timer(0.1, self._window.destroy).start()
            return
        self.engine.isRunning = False
        if hasattr(self.engine, 'server_socket'):
            helper.close_socket(self.engine)
        helper.dump_settings(self.engine)
        self.engine.logger.info('bye~')
        self._stop_listener()
        self.threadPool.shutdown(wait=False)
        threading.Timer(0.1, self._window.destroy).start()

    def playback(self):
        if self.engine.isRunning:
            self.engine.logger.info('stopping playback')
            self.engine.isRunning = False
            return

    def list_recordings(self):
        rec_dir = os.path.join(constants.ROOT_PATH, constants.RECORDING_DIR_NAME)
        if not os.path.isdir(rec_dir):
            return []
        files = []
        for f in sorted(os.listdir(rec_dir), reverse=True):
            if f.endswith('.f6rec.json') or f.endswith('.f6rec.json.gz'):
                fp = os.path.join(rec_dir, f)
                try:
                    meta = PlaybackSource.load_metadata(fp)
                    files.append({
                        'name': f,
                        'path': fp,
                        'packets': meta.get('packet_count', 0),
                        'duration': round(meta.get('duration_sec', 0), 1)
                    })
                except Exception:
                    pass
        return files

    def start_playback(self, filepath):
        if self.engine.isRunning:
            self.engine.logger.info('stopping current run before playback')
            self.engine.isRunning = False

        try:
            meta = PlaybackSource.load_metadata(filepath)
            self.logger.info(
                f'[Playback] {meta["packet_count"]} packets, {meta["duration_sec"]:.1f}s')
        except Exception as e:
            self.logger.error(f'[Playback] failed to load: {e}')
            return

        self._reset_dashboard()
        self.engine.isRunning = True

        def _playback_then_resume():
            self.engine.run_playback(filepath,
                                     self.update_tree, self.update_car_info)
            # Auto-resume live mode after playback ends
            if self._auto_live and not self._closing:
                self.logger.info('[Playback] ended, resuming live telemetry')
                self.run()

        self.threadPool.submit(_playback_then_resume)

    # ---- Settings handlers ----

    def set_language(self, lang_index):
        self.language = int(lang_index)
        self._push_i18n()

    def set_clutch(self, enabled):
        self.engine.enable_clutch = bool(enabled)

    def set_shortcut(self, key_name, value):
        setattr(self.engine, key_name, value)
        self.logger.info(f'{key_name} shortcut is: {value}')

    def toggle_record(self, enabled):
        self._record_enabled = bool(enabled)

    def toggle_farm(self, enabled):
        self.engine.farming = bool(enabled)

    def toggle_offroad(self, enabled):
        self.engine.shift_point_factor = (
            constants.OFFROAD_RALLY_SHIFT_FACTOR if enabled
            else constants.SHIFT_FACTOR)

    # ---- Query methods (called from JS) ----

    def get_themes(self):
        return [{'id': k, 'name': v[0]} for k, v in THEMES.items()]

    def switch_theme(self, theme_name):
        html = _load_theme_html(theme_name)
        if html and self._window:
            # Delay load_html so pywebview can complete the JS return callback first
            threading.Timer(0.15, lambda: self._window.load_html(html) if not self._closing else None).start()

    def set_setting(self, key, value):
        if key == 'ip':
            self.engine.ip = value
        elif key == 'port':
            self.engine.port = int(value)

    def get_settings(self):
        if not self.engine:
            return {
                'ip': constants.IP,
                'port': constants.PORT,
                'language': self.language,
                'clutch': constants.ENABLE_CLUTCH,
                'farm': False,
                'offroad': False,
                'shortcuts': {
                    'clutch': constants.CLUTCH,
                    'upshift': constants.UPSHIFT,
                    'downshift': constants.DOWNSHIFT,
                }
            }
        return {
            'ip': self.engine.ip,
            'port': self.engine.port,
            'language': self.language,
            'clutch': self.engine.enable_clutch,
            'farm': self.engine.farming,
            'offroad': self.engine.shift_point_factor == constants.OFFROAD_RALLY_SHIFT_FACTOR,
            'shortcuts': {
                'clutch': self.engine.clutch,
                'upshift': self.engine.upshift,
                'downshift': self.engine.downshift,
            }
        }

    def get_i18n(self):
        fields = [
            'SELECT_LANGUAGE_TXT', 'LANGUAGE_TXT', 'CLUTCH_SHORTCUT_TXT',
            'UPSHIFT_SHORTCUT_TXT', 'DOWNSHIFT_SHORTCUT_TXT', 'CLUTCH_TXT',
            'FARM_TXT', 'OFFROAD_RALLY_TXT', 'CAR_ID', 'CAR_PERF',
            'CAR_DRIVETRAIN', 'CAR_CLASS_TXT', 'TIRE_INFORMATION_TXT',
            'ACCEL_TXT', 'BRAKE_TXT', 'SHIFT_POINT_TXT', 'SPEED_TXT', 'RPM_TXT',
            'BOOST_TXT', 'FUEL_TXT', 'GEAR_TXT', 'THROTTLE_TXT', 'POWER_TXT',
            'TORQUE_TXT', 'LAP_TXT', 'BEST_LAP_TXT', 'LAST_LAP_TXT',
            'CUR_LAP_TXT', 'RACE_POS_TXT', 'RACE_TIME_TXT', 'PITCH_TXT',
            'ROLL_TXT', 'STEER_TXT', 'DIST_TXT', 'CONNECTION_TXT',
            'DISPLAY_THEME_TXT', 'SUSP_TRAVEL_TXT',
            'LOG_TAB_TXT', 'CHARTS_TAB_TXT', 'SHIFT_POINTS_TAB_TXT',
            'SETTINGS_TITLE', 'CONFIRM_TXT',
            'COLLECT_BUTTON_TXT', 'ANALYSIS_BUTTON_TXT', 'RUN_BUTTON_TXT',
            'PAUSE_BUTTON_TXT', 'EXIT_BUTTON_TXT', 'RECORD_TXT', 'PLAYBACK_TXT',
            'PROGRAM_INFO_TXT', 'LIVE_TORQUE_TAB_TXT', 'CLEAR_LOG_TXT',
        ]
        result = {}
        for field in fields:
            val = getattr(constants, field, None)
            if val is not None and isinstance(val, (list, tuple)):
                result[field] = val
        return result

    def get_available_shortcuts(self, current_key):
        all_bound = self.engine.boundKeys() + list(constants.BOUND_KEYS)
        return [k for k in keyboard_helper.key_list
                if k not in all_bound or k == current_key]

    def render_charts(self):
        self._render_charts()

    def clear_log(self):
        self._js_call("var e=document.getElementById('logContent')||document.getElementById('logPanel');if(e)e.textContent=''")

    # ---- Callbacks from Forza engine ----

    def update_tree(self):
        if len(self.engine.shift_point) == 0:
            return
        data = {}
        for key, value in self.engine.shift_point.items():
            data[str(key)] = {
                'speed': round(value['speed'], 1),
                'rpm': round(value['rpmo']),
            }
        self._js_call(f"updateShiftPoints({json.dumps(data)})")

    def update_car_info(self, fdp):
        if not self.engine.isRunning:
            return

        gear = fdp.gear
        ratio = self.engine.gear_ratios.get(gear, {}).get('ratio', None)
        output_torque = fdp.torque / ratio if ratio and ratio > 0 else None

        data = {
            'car_ordinal': fdp.car_ordinal,
            'car_perf': fdp.car_performance_index,
            'car_class': constants.CAR_CLASS_LIST[fdp.car_class] if 0 <= fdp.car_class < len(constants.CAR_CLASS_LIST) else str(fdp.car_class),
            'drivetrain': constants.CAR_DRIVETRAIN_LIST[fdp.drivetrain_type] if 0 <= fdp.drivetrain_type < len(constants.CAR_DRIVETRAIN_LIST) else str(fdp.drivetrain_type),
            'speed': round(fdp.speed * constants.MS_TO_KMH, 1),
            'rpm': round(fdp.current_engine_rpm),
            'gear': fdp.gear,
            'engine_max_rpm': fdp.engine_max_rpm,
            'accel': fdp.accel,
            'brake': fdp.brake,
            'accel_x': round(fdp.acceleration_x, 3),
            'accel_z': round(fdp.acceleration_z, 3),
            'boost': fdp.boost,
            'fuel': fdp.fuel,
            'torque': fdp.torque,
            'output_torque': round(output_torque, 1) if output_torque else None,
            'power': round(fdp.power / constants.W_TO_KW, 1),
            'clutch': fdp.clutch,
            'handbrake': fdp.handbrake,
            'steer': round(fdp.steer, 3),
            'engine_idle_rpm': fdp.engine_idle_rpm,
            'accel_y': round(fdp.acceleration_y, 3),
            'yaw_rate': round(fdp.angular_velocity_x, 2),
            'yaw': round(fdp.yaw, 2),
            'pitch': round(fdp.pitch, 2),
            'roll': round(fdp.roll, 2),
            'position_x': round(fdp.position_x, 2),
            'position_y': round(fdp.position_y, 2),
            'position_z': round(fdp.position_z, 2),
            'best_lap_time': fdp.best_lap_time,
            'last_lap_time': fdp.last_lap_time,
            'cur_lap_time': fdp.cur_lap_time,
            'lap_no': fdp.lap_no,
            'race_pos': fdp.race_pos,
            'cur_race_time': fdp.cur_race_time,
            'dist_traveled': round(fdp.dist_traveled, 1),
            'num_cylinders': fdp.num_cylinders,
            'norm_driving_line': fdp.norm_driving_line,
            'norm_ai_brake_diff': fdp.norm_ai_brake_diff,
            'combined_slip_FL': round(fdp.tire_combined_slip_FL, 3),
            'combined_slip_FR': round(fdp.tire_combined_slip_FR, 3),
            'combined_slip_RL': round(fdp.tire_combined_slip_RL, 3),
            'combined_slip_RR': round(fdp.tire_combined_slip_RR, 3),
            'tires': {
                'FL': {'temp': round(fdp.tire_temp_FL), 'slip': round(abs(fdp.tire_combined_slip_FL), 3),
                       'susp': round(fdp.norm_suspension_travel_FL, 3),
                       'slip_ratio': round(fdp.tire_slip_ratio_FL, 3),
                       'slip_angle': round(fdp.tire_slip_angle_FL, 3),
                       'combined_slip': round(fdp.tire_combined_slip_FL, 3),
                       'susp_meters': round(fdp.suspension_travel_meters_FL, 4),
                       'wheel_speed': round(fdp.wheel_rotation_speed_FL)},
                'FR': {'temp': round(fdp.tire_temp_FR), 'slip': round(abs(fdp.tire_combined_slip_FR), 3),
                       'susp': round(fdp.norm_suspension_travel_FR, 3),
                       'slip_ratio': round(fdp.tire_slip_ratio_FR, 3),
                       'slip_angle': round(fdp.tire_slip_angle_FR, 3),
                       'combined_slip': round(fdp.tire_combined_slip_FR, 3),
                       'susp_meters': round(fdp.suspension_travel_meters_FR, 4),
                       'wheel_speed': round(fdp.wheel_rotation_speed_FR)},
                'RL': {'temp': round(fdp.tire_temp_RL), 'slip': round(abs(fdp.tire_combined_slip_RL), 3),
                       'susp': round(fdp.norm_suspension_travel_RL, 3),
                       'slip_ratio': round(fdp.tire_slip_ratio_RL, 3),
                       'slip_angle': round(fdp.tire_slip_angle_RL, 3),
                       'combined_slip': round(fdp.tire_combined_slip_RL, 3),
                       'susp_meters': round(fdp.suspension_travel_meters_RL, 4),
                       'wheel_speed': round(fdp.wheel_rotation_speed_RL)},
                'RR': {'temp': round(fdp.tire_temp_RR), 'slip': round(abs(fdp.tire_combined_slip_RR), 3),
                       'susp': round(fdp.norm_suspension_travel_RR, 3),
                       'slip_ratio': round(fdp.tire_slip_ratio_RR, 3),
                       'slip_angle': round(fdp.tire_slip_angle_RR, 3),
                       'combined_slip': round(fdp.tire_combined_slip_RR, 3),
                       'susp_meters': round(fdp.suspension_travel_meters_RR, 4),
                       'wheel_speed': round(fdp.wheel_rotation_speed_RR)},
            },
        }
        self._js_call(f"onTelemetry({json.dumps(data)})")

    # ---- Internal helpers ----

    @staticmethod
    def _listener_alive(listener):
        if listener is None:
            return False
        alive = getattr(listener, 'is_alive', None)
        if alive is None:
            return True
        return alive() if callable(alive) else alive

    def _stop_listener(self):
        """Stop the keyboard listener safely (idempotent)."""
        with self._listener_lock:
            listener = self.listener
            self.listener = None
            self._listener_start_requested = False
            if self._listener_alive(listener):
                threading.Thread(target=listener.stop, daemon=True).start()

    def start_listener(self):
        """Start the keyboard listener if not already running (idempotent)."""
        with self._listener_lock:
            if self._listener_start_requested and self._listener_alive(self.listener):
                return  # Already started or starting

            self._listener_start_requested = True
            # Ensure any existing listener is stopped first
            if self._listener_alive(self.listener):
                # Stop without resetting _listener_start_requested
                listener = self.listener
                self.listener = None
                if self._listener_alive(listener):
                    threading.Thread(target=listener.stop, daemon=True).start()
                # Don't sleep here - let it stop asynchronously
                # The new listener will be created immediately

            try:
                self.listener = KeyboardListener(on_press=self._on_key_press)
                self.listener.start()
            except Exception as e:
                self._listener_start_requested = False
                if self.logger:
                    self.logger.warning(f"Failed to start keyboard listener: {e}")

    def _save_recorder(self):
        if self.engine.recorder is not None:
            try:
                path = self.engine.recorder.save(metadata={
                    'format': self.engine.packet_format,
                    'car_ordinal': self.engine.ordinal,
                })
                self.engine.logger.info(
                    f'[Record] saved: {path} ({self.engine.recorder.packet_count} packets)')
            except ValueError as e:
                self.engine.logger.warning(f'[Record] save skipped: {e}')
            finally:
                self.engine.recorder = None

    def _reset_dashboard(self):
        self._js_call("resetDashboard()")

    def _on_key_press(self, key):
        try:
            if key == constants.SHOW_LIVE:
                self._js_call("document.querySelector('.tab-btn[data-tab=\"live\"]').click()")
            elif key == constants.COLLECT_DATA:
                self.collect()
            elif key == constants.ANALYSIS:
                self.analyze()
            elif key == constants.AUTO_SHIFT:
                self.run()
            elif key == constants.STOP:
                self.pause()
            elif key == constants.RECORD:
                self._record_enabled = not self._record_enabled
                self.toggle_record(self._record_enabled)
        except BaseException as e:
            self.engine.logger.exception(e)

    def _push_settings(self):
        settings = self.get_settings()
        self._js_call(f"updateSettings({json.dumps(settings)})")

    def _push_i18n(self):
        i18n = self.get_i18n()
        self._js_call(f"updateI18n({json.dumps(i18n)}, {self.language})")

    def _push_live_torque_data(self):
        if len(self.engine.records) == 0:
            return
        from collections import defaultdict
        BIN = 100
        by_gear = defaultdict(list)
        for rec in self.engine.records:
            g = rec.get('gear')
            if g and rec.get('torque', 0) > 0:
                by_gear[g].append((int(rec['rpm']), round(rec['torque'], 1)))
        data = {}
        for gear in sorted(by_gear.keys()):
            bins = defaultdict(list)
            for rpm, tq in by_gear[gear]:
                bins[(rpm // BIN) * BIN].append(tq)
            rpm_torque = {str(k): round(sum(v) / len(v), 1) for k, v in sorted(bins.items())}
            data[str(gear)] = {'rpm_torque_map': rpm_torque}
        self.logger.info(f'[LiveTorque] sending {sum(len(v["rpm_torque_map"]) for v in data.values())} bins across {len(data)} gears')
        self._js_call(f"updateLiveTorqueData({json.dumps(data)})")

    def _render_charts(self):
        if len(self.engine.gear_ratios) == 0:
            return
        try:
            data = {}
            max_pts = 200
            for g, item in self.engine.rpm_torque_map.items():
                ratio = self.engine.gear_ratios[g]['ratio']
                raw = self.engine.get_gear_raw_records(g)
                records = raw[item['min_rpm_index']:item['max_rpm_index']]
                step = max(1, len(records) // max_pts)
                rpm_torque = sorted([[r['rpm'], round(r['torque'] / ratio, 1)] for r in records[::step]])
                speed_torque = sorted([[round(r['speed'] * constants.MS_TO_KMH, 1), round(r['torque'] / ratio, 1)] for r in records[::step]])
                data[str(g)] = {
                    'ratio': round(ratio, 3),
                    'rpm_torque': rpm_torque,
                    'speed_torque': speed_torque,
                }
            self.logger.info(f'[Charts] sending {len(data)} gears analysis data')
            self._js_call(f"updateCharts({json.dumps(data)})")
        except Exception as e:
            self.logger.warning(f'Chart data send failed: {e}')


class WebWindow:
    """Creates and manages the pywebview window."""

    def __init__(self, theme='supercar'):
        self.api = Api()
        theme_html = _load_theme_html(theme)
        self.window = webview.create_window(
            "Forza Horizon 5: Auto Gear Shifting - Web Edition",
            html=theme_html,
            width=1920,
            height=1080,
            min_size=(1200, 800),
            js_api=self.api,
            on_top=False,
        )
        self.api.set_window(self.window)
        self.window.events.closing += self._on_closing

    def _on_closing(self):
        self.api._closing = True
        if self.api.engine:
            self.api.engine.isRunning = False
            if hasattr(self.api.engine, 'server_socket'):
                helper.close_socket(self.api.engine)
        self.api._stop_listener()
        if self.api.threadPool:
            self.api.threadPool.shutdown(wait=False)

    def start(self):
        webview.start(debug=False)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Horizon6AutoGear Web GUI')
    parser.add_argument('--theme', default='phantom', choices=list(THEMES.keys()),
                        help='UI theme (default: phantom)')
    args = parser.parse_args()
    app = WebWindow(theme=args.theme)
    app.start()


if __name__ == "__main__":
    main()
