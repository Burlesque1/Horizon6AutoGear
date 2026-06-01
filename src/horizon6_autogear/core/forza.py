# Standard library
import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from os import listdir
from os.path import isfile, join

# Third-party
import matplotlib.pyplot as plt

# Local
import horizon6_autogear.config.config as constants

from horizon6_autogear.core.forza_data_packet import ForzaDataPacket

import horizon6_autogear.shifting.gear_helper as gear_helper
import horizon6_autogear.utils.helper as helper
import horizon6_autogear.shifting.keyboard as keyboard_helper
from horizon6_autogear.core.car_info import CarInfo
from horizon6_autogear.config.config import ConfigVersion
from horizon6_autogear.utils.logger import Logger
from horizon6_autogear.core.playback import PlaybackSource
from horizon6_autogear.shifting.output_device import SharedState
from horizon6_autogear.shifting.shift_controller import ShiftController
from horizon6_autogear.shifting.keyboard import KeyboardOutput
from horizon6_autogear.control.traction_controller import TractionController
from horizon6_autogear.control.arbiter import Arbiter
from horizon6_autogear.control.corner_controller import CornerController

debug_properties = [
    'gear', 'current_engine_rpm', 'speed', 'tire_slip_ratio_RL', 'tire_slip_ratio_RR', 'tire_slip_ratio_FL', 'tire_slip_ratio_FR', 'tire_slip_angle_RL', 'tire_slip_angle_RR', 'tire_slip_angle_FL', 'tire_slip_angle_FR', 'acceleration_x', 'acceleration_y',
    'acceleration_z', 'velocity_x', 'velocity_y', 'velocity_z', 'accel', 'surface_rumble_FL', 'surface_rumble_FR', 'surface_rumble_RL', 'surface_rumble_RR', 'norm_driving_line', 'norm_ai_brake_diff', 'brake',
]


class Forza(CarInfo):

    def __init__(self, threadPool: ThreadPoolExecutor, logger: Logger = None, packet_format='fh6', enable_clutch=False):
        """initialization

        Args:
            threadPool (ThreadPoolExecutor): threadPool
            packet_format (str, optional): packet_format. Defaults to 'fh6'.
            enable_clutch (bool, optional): enable_clutch. Defaults to False.
        """
        super().__init__()

        # === socket ===
        self.ip = constants.IP
        self.port = constants.PORT

        # === logger ===
        self.logger = (Logger()(constants.LOGGER_NAME)) if logger is None else logger

        self.packet_format = packet_format
        self.isRunning = False
        self.threadPool = threadPool
        self.enable_clutch = enable_clutch
        self.farming = False
        self.shift_point_factor = constants.SHIFT_FACTOR

        # shortcuts
        self.clutch = constants.CLUTCH
        self.upshift = constants.UPSHIFT
        self.downshift = constants.DOWNSHIFT
        self.boundKeys = lambda: [self.clutch, self.upshift, self.downshift]

        # constant
        self.config_folder = os.path.join(constants.ROOT_PATH, constants.CONFIG_DIR_NAME)

        # create folders if not existed
        helper.ensure_folder_exists(self.config_folder)

        # init constants from config if existed
        helper.load_settings(self)

        # === car data ===
        self.gear_ratios = {}
        self.rpm_torque_map = {}
        self.shift_point = {}
        self.records = []

        # === exp farm setting ===
        self.reset_car = 0
        self.isBrake = False
        self.reset_time = time.time()
        self.break_timer = time.time()

        # === recording / playback ===
        self.playback_mode = False
        self.recorder = None
        self.shared_state = SharedState()
        self.output_device = KeyboardOutput(
            clutch_enabled=self.enable_clutch,
            farming=self.farming,
        )
        self.shift_controller = None
        self.tcs_enabled = constants.TCS_ENABLED
        self.traction_controller = TractionController(
            slip_threshold=constants.TCS_SLIP_THRESHOLD,
            min_speed=constants.TCS_MIN_SPEED,
            throttle_reduction=constants.TCS_THROTTLE_REDUCTION,
        )
        self.arbiter = Arbiter()
        self.corner_controller = CornerController()

    def test_gear(self, update_car_gui_func=None, data_source=None):
        """collect gear information

        Args:
            update_car_gui_func (optional): callback to update car gui. Defaults to None.
            data_source (optional): socket or PlaybackSource. Defaults to None (creates UDP socket).
        """
        try:
            self.logger.debug('[Collect] started')
            if data_source is None:
                helper.create_socket(self)
            socket_to_use = data_source if data_source is not None else self.server_socket
            self.records = []
            refresh_time = time.time()
            while self.isRunning:
                fdp = helper.nextFdp(socket_to_use, self.packet_format)
                if fdp is None:
                    continue

                if fdp.speed > constants.SPEED_THRESHOLD:
                    # Skip invalid gears (0 = neutral/reverse, out of range)
                    if fdp.gear < constants.DEFAULT_MIN_GEAR or fdp.gear > constants.DEFAULT_MAX_GEAR:
                        continue
                    # Skip when RPM is 0 (coasting/engine off) to avoid division by zero
                    if fdp.current_engine_rpm <= 0:
                        continue
                    self.__update_forza_info(fdp, dump=False)
                    if update_car_gui_func is not None and time.time() - refresh_time > constants.GUI_REFRESH_INTERVAL:
                        update_car_gui_func(fdp)
                        refresh_time = time.time()
                    info = {
                        'gear': fdp.gear,
                        'rpm': fdp.current_engine_rpm,
                        'time': time.time(),
                        'speed': fdp.speed * constants.MS_TO_KMH,
                        'slip': min(constants.MAX_SLIP_RATIO, (fdp.tire_slip_ratio_RL + fdp.tire_slip_ratio_RR) / 2),
                        'clutch': fdp.clutch,
                        'power': fdp.power / constants.W_TO_KW,
                        'torque': fdp.torque,
                        'speed/rpm': fdp.speed * constants.MS_TO_KMH / fdp.current_engine_rpm
                    }
                    self.records.append(info)
                    self.logger.debug(info)
        except Exception as e:
            self.logger.exception(e)
        finally:
            self.isRunning = False
            if data_source is None:
                helper.close_socket(self)
            if len(self.records) > 0:
                gears = set(item['gear'] for item in self.records)
                self.logger.info(f'[Collect] finished: {len(self.records)} samples across gears {sorted(gears)}')
            else:
                self.logger.warning('[Collect] finished: no data collected')
            self.logger.debug('[Collect] ended')

    def analyze(self, performance_profile: bool = True, is_gui: bool = False):
        """analyze data

        Args:
            performance_profile (bool, optional): plot figures or not. Defaults to True.
            is_guid (bool, optional): is gui. Defaults to False
        """
        try:
            self.logger.debug('[Analyze] started')
            self.shift_point = gear_helper.calculate_optimal_shift_point(self)
            helper.dump_config(self)

            if performance_profile:
                plt.close()
                if is_gui:
                    plt.ion()

                fig, ax = plt.subplots(2, 2)
                fig.tight_layout()

                # # gear vs ratio at 0, 0
                helper.plot_gear_ratio(self, ax, 0, 0)

                # torque vs rpm at 0, 1
                helper.plot_torque_rpm(self, ax, 0, 1)

                # torque vs speed at 1, 0
                helper.plot_torque_speed(self, ax, 1, 0)

                # rpm vs speed at 1, 1
                helper.plot_rpm_speed(self, ax, 1, 1)
                plt.show()
        except Exception as e:
            self.logger.exception(e)
            self.logger.error(f"[Analyze] Failed: {e}. Try re-collecting data with the car in forward motion")
        finally:
            self.logger.debug('[Analyze] ended')

    def __update_forza_info(self, fdp: ForzaDataPacket, update_tree_func=lambda *args: None, dump: bool = True, first_load: bool = False):
        """update forza info while running

            # try to load config if:
            # self.ordinal != fdp.car_ordinal or self.car_perf != fdp.car_performance_index or self.car_class != fdp.car_class or self.car_drivetrain != fdp.drivetrain_type

        Args:
            fdp (ForzaDataPacket): datapackage
        """
        if first_load or self.ordinal != fdp.car_ordinal or self.car_perf != fdp.car_performance_index or self.car_class != fdp.car_class or self.car_drivetrain != fdp.drivetrain_type:
            self.ordinal = fdp.car_ordinal
            self.car_perf = fdp.car_performance_index
            self.car_class = fdp.car_class
            self.car_drivetrain = fdp.drivetrain_type
            res = True
            if dump:
                res = self.__try_auto_load_config(fdp)

            if not res:
                self.shift_point = {}

            if update_tree_func is not None:
                self.threadPool.submit(update_tree_func)

            return res
        else:
            return True

    def __try_auto_load_config(self, fdp: ForzaDataPacket):
        """auto load config while driving

        Args:
            fdp (ForzaDataPacket): fdp

        Returns:
            [bool]: success or failure
        """
        try:
            self.logger.debug('[Config] auto-load started')
            configs = [f for f in listdir(self.config_folder) if (isfile(join(self.config_folder, f)) and str(fdp.car_ordinal) in f)]
            if len(configs) <= 0:
                self.logger.warning(f'[Config] car {fdp.car_ordinal} config not found in {self.config_folder}. Run {constants.COLLECT_DATA} + {constants.ANALYSIS} first')
                return False
            elif len(configs) > 0:
                self.logger.info(f'[Config] found car {fdp.car_ordinal} config(s): {configs}')

                # latest config version: ordinal-perf-drivetrain.json, v2
                filename = helper.get_config_name(self)
                if filename in configs:
                    if self.__try_loading_config(filename):
                        # remove legacy config if necessary
                        if len(configs) > 1:
                            self.__cleanup_legacy_config(configs)

                        return True
                    else:
                        return False

                # if latest config version not existed. like only ordinal.json, v1
                filename = helper.get_config_name(self, ConfigVersion.v1)
                if filename in configs:
                    if self.__try_loading_config(filename):
                        self.car_perf = fdp.car_performance_index
                        self.car_class = fdp.car_class
                        self.car_drivetrain = fdp.drivetrain_type

                        # dump to latest config version
                        helper.dump_config(self)
                        self.__cleanup_legacy_config(configs)
                        return True
                    else:
                        return False

                # unknown config
                self.logger.warning(f'[Config] valid config for car {fdp.car_ordinal} not found in {self.config_folder}: {configs}. Run {constants.COLLECT_DATA} + {constants.ANALYSIS} to create')
                return False
        finally:
            self.logger.debug('[Config] auto-load ended')

    def __cleanup_legacy_config(self, configs, latest_version: ConfigVersion = constants.DEFAULT_CONFIG_VERSION):
        """cleanup legacy configs

        Args:
            configs (list): list of configs
            latest_version (ConfigVersion, optional): config version. Defaults to constants.DEFAULT_CONFIG_VERSION.
        """
        for config in configs:
            version = helper.get_config_version(self, config)
            if version != latest_version:
                try:
                    self.logger.warning(f'[Config] removing legacy config: {config}')
                    os.remove(self.get_config_path(config))
                except Exception as e:
                    self.logger.warning(f'[Config] failed to remove legacy config {config}: {e}')

    def __try_loading_config(self, config):
        """try to load config

        Args:
            config (str): config file name

        Returns:
            bool: success or failure
        """
        self.logger.info(f'[Config] loading: {config}')
        helper.load_config(self, self.get_config_path(config))
        if len(self.shift_point) <= 0:
            self.logger.warning(f'[Config] invalid config. Run {constants.COLLECT_DATA} + {constants.ANALYSIS} to create a new one')
            return False

        self.logger.info(f'[Config] loaded: {config}')
        return True

    def _init_shift_controller(self):
        """Initialize shift controller with current car config."""
        self.shift_controller = ShiftController(
            output_device=self.output_device,
            min_gear=self.minGear,
            max_gear=self.maxGear,
            drivetrain=self.car_drivetrain,
            shift_factor=self.shift_point_factor,
            logger=self.logger,
        )
        self.shift_controller.shift_point = self.shift_point

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

        corner_throttle, corner_brake = self.corner_controller.compute(fdp)

        commanded = self.arbiter.resolve(
            driver_throttle=driver_throttle,
            tcs_throttle=tcs_throttle,
            corner_throttle=corner_throttle,
            corner_brake=corner_brake,
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

    def set_output_device(self, device):
        """Swap output device at runtime. Updates ShiftController reference."""
        old = self.output_device
        old.release_all()
        self.output_device = device
        if self.shift_controller is not None:
            self.shift_controller.output_device = device
        self.logger.info(f'[Output] switched to {type(device).__name__}')

    def __exp_farming_setup(self, fdp):
        """exp farming setup

        Args:
            fdp (ForzaDataPacket): datapackage
        """
        if self.farming and fdp.car_ordinal > 0:
            # enable reset car if exp or sp farming is True
            if abs(fdp.norm_driving_line) >= constants.RESET_DRIVING_LINE_THRESHOLD or fdp.speed < constants.RESET_MIN_SPEED:
                self.reset_car = self.reset_car + 1
                # reset car position
                if self.reset_car >= constants.RESET_COUNT_THRESHOLD and time.time() - self.reset_time > constants.RESET_COOLDOWN_SECONDS:
                    self.reset_car = 0
                    self.threadPool.submit(keyboard_helper.resetcar, self)
                    self.reset_time = time.time()
            else:
                self.reset_car = 0

            # exp or sp farming to avoid afk detection, 30s interval
            if time.time() - self.break_timer > constants.FARMING_BRAKE_INTERVAL and fdp.norm_ai_brake_diff > 0:
                self.threadPool.submit(keyboard_helper.press_brake, self)
                self.break_timer = time.time()

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

                    # Safe: single-writer main thread. Only this thread checks and sets
                    # shift_pending; worker threads only clear it in finally blocks.
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

    def run_playback(self, recording_path: str, update_tree_func=lambda *args: None, update_car_gui_func=lambda *args: None):
        """Replay recorded UDP data. No socket, no farming, no key presses.

        Args:
            recording_path (str): path to .f6rec.json file
            update_tree_func: callback to update tree view
            update_car_gui_func: callback to update car gui
        """
        self.playback_mode = True
        source = None
        try:
            self.logger.info(f'[Playback] loading: {recording_path}')
            source = PlaybackSource(recording_path)
            if source.packet_format != self.packet_format:
                self.logger.warning(f'[Playback] format mismatch: recording={source.packet_format}, session={self.packet_format}')
            self.logger.info(f'[Playback] {source.metadata["packet_count"]} packets, {source.metadata["duration_sec"]:.1f}s')

            self.test_gear(data_source=source, update_car_gui_func=update_car_gui_func)

            cur, total = source.progress
            self.logger.info(f'[Playback] finished: {cur}/{total} packets processed')
        except ValueError as e:
            self.logger.error(f'[Playback] validation failed: {e}')
        except Exception as e:
            self.logger.exception(e)
        finally:
            self.isRunning = False
            self.playback_mode = False
            self.logger.debug('[Playback] ended')
