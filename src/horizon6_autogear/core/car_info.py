# Standard library

# Local utilities (stdlib-only to avoid circular dependency)
from horizon6_autogear.utils.path_utils import get_config_path
from horizon6_autogear.config.config import DEFAULT_MIN_GEAR, DEFAULT_MAX_GEAR

class CarInfo():

    def __init__(self):
        """initialization
        """
        # === Car information ===
        self.ordinal = -1
        self.car_perf = 0
        self.car_class = -1
        self.car_drivetrain = -1
        self.minGear = DEFAULT_MIN_GEAR
        self.maxGear = DEFAULT_MAX_GEAR

        self.gear_ratios = {}
        self.rpm_torque_map = {}
        self.shift_point = {}
        self.records = []

        # === logger ===
        self.logger = None
        self.config_folder = None

    def get_gear_raw_records(self, g: int):
        """get raw records for gear

        Args:
            g (int): gear

        Returns:
            [list]: list of recrods for gear
        """
        return [item for item in self.records if item['gear'] == g]

    def get_config_path(self, filename: str) -> str:
        """Get full path to config file

        Args:
            filename (str): config file name

        Returns:
            str: full path to config file
        """
        return get_config_path(self.config_folder, filename)
