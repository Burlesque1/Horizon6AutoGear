import enum
import os
from pynput.keyboard import Key


# config version
class ConfigVersion(enum.Enum):
    v1 = 1
    v2 = 2


DEFAULT_CONFIG_VERSION = ConfigVersion.v2

# repo path
# Get project root directory (3 levels up from src/horizon6_autogear/config/)
ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SETTING_FILENAME = 'settings.json'

# socket information
IP = os.environ.get('FORZA_UDP_IP', '0.0.0.0')
PORT = int(os.environ.get('FORZA_UDP_PORT', '54321'))

# data format
PACKET_FORMAT = 'fh6'

# clutch setup
ENABLE_CLUTCH = True

# default car config
EXAMPLE_CAR_ORDINAL = 'example'

# === UI settings ===
BACKGROUND_COLOR = "#1a181a"
TEXT_COLOR = "#a1a1a1"
PERF_STICKER_BACKGROUND = "#FFFFFF"

# car info relx, rely
CAR_INFO_LEFTBOUND_RELX = 0.08
CAR_INFO_RIGHTBOUND_RELX = 0.9
CAR_INFO_TOPBOUND_RELY = 0.195
CAR_INFO_BOTTOMBOUND_RELY = 0.815
CAR_INFO_LINE_GAP = 0.065

# car drivetrain
DRIVETRAIN_FWD = 0
DRIVETRAIN_RWD = 1
DRIVETRAIN_AWD = 2
DRIVETRAIN_UNKNOWN = -1

CAR_DRIVETRAIN_LIST = [
    ('FWD', '前驱'),
    ('RWD', '后驱'),
    ('AWD', '四驱'),
    ('N', 'N')
]

# tire canvas info: Position: [start_x1_factor, start_y1_factor, s radius]
X_PADDING_LEFT = 0.025
X_PADDING_RIGHT = 0.025
Y_PADDING_TOP = 0.075
Y_PADDING_BOT = 0.025
TIRE_RECT_WIDTH = 0.1
TIRE_RECT_HEIGHT = 0.25
TIRE_X_SPACING = 0.1
TIRE_Y_SPACING = 0.1
RADIUS = 12
TIRE_CANVAS_RELX = 0.5
TIRE_CANVAS_RELY = 0.5
TIRE_CANVAS_RELWIDTH = TIRE_RECT_WIDTH * 2 + TIRE_X_SPACING + X_PADDING_LEFT + X_PADDING_RIGHT
TIRE_CANVAS_RELHEIGHT = TIRE_RECT_HEIGHT * 2 + TIRE_Y_SPACING + Y_PADDING_TOP + Y_PADDING_BOT
TIRES = {
    "FL": [X_PADDING_LEFT, Y_PADDING_TOP, X_PADDING_LEFT + TIRE_RECT_WIDTH, Y_PADDING_TOP + TIRE_RECT_HEIGHT, RADIUS],
    "FR": [X_PADDING_LEFT + TIRE_RECT_WIDTH + TIRE_X_SPACING, Y_PADDING_TOP, X_PADDING_LEFT + TIRE_RECT_WIDTH * 2 + TIRE_X_SPACING, Y_PADDING_TOP + TIRE_RECT_HEIGHT, RADIUS],
    "RL": [X_PADDING_LEFT, Y_PADDING_TOP + TIRE_RECT_HEIGHT + TIRE_Y_SPACING, X_PADDING_LEFT + TIRE_RECT_WIDTH, Y_PADDING_TOP + TIRE_RECT_HEIGHT * 2 + TIRE_Y_SPACING, RADIUS],
    "RR": [X_PADDING_LEFT + TIRE_RECT_WIDTH + TIRE_X_SPACING, Y_PADDING_TOP + TIRE_RECT_HEIGHT + TIRE_Y_SPACING, X_PADDING_LEFT + TIRE_RECT_WIDTH * 2 + TIRE_X_SPACING, Y_PADDING_TOP + TIRE_RECT_HEIGHT * 2 + TIRE_Y_SPACING, RADIUS]
}

# car class mapping
CAR_CLASS_LIST = ['D', 'C', 'B', 'A', 'S1', 'S2', 'X', "N"]
CAR_CLASS_COLOR = ['#3dafd1', '#edc786', '#f28240', '#e22b2a', '#8729e2', '#3256ba', '#46ce67', TEXT_COLOR]

# === short-cut ===
SHOW_LIVE = Key.f1  # switch to live tab
COLLECT_DATA = Key.f2
ANALYSIS = Key.f3
AUTO_SHIFT = Key.f4
RECORD = Key.f5  # toggle recording
OBSERVE = Key.f6  # display-only mode (no shifting)
STOP = Key.f9  # stop program
CLOSE = Key.f12  # close program (legacy GUIs only)

# === Keyboard ===
CLUTCH = 'i'  # clutch
UPSHIFT = 'e'  # up shift
DOWNSHIFT = 'q'  # down shift
ACCELERATION = 'w'  # acceleration
BRAKE = 's'  # brake
BOUND_KEYS = [SHOW_LIVE.name, STOP.name, COLLECT_DATA.name, ANALYSIS.name, AUTO_SHIFT.name, OBSERVE.name, RECORD.name]

# === Delay Settings ===
DELAY_CLUTCH_TO_SHIFT = 0  # delay between pressing clutch and shift
DELAY_SHIFT_TO_CLUTCH = 0.06  # delay between pressing shift and releasing clutch
DOWN_SHIFT_COOL_DOWN = 0.35  # cooldown after down shift
UP_SHIFT_COOL_DOWN = 0.35  # cooldown after up shift
BLIP_THROTTLE_DURATION = 0.12  # blip the throttle duration. Should be short since keyboard is 100% acceleration output

# === Keyboard Timing Constants ===
KEY_PRESS_DURATION = 0.05  # duration for brief key presses
MENU_DELAY = 0.3  # delay for menu navigation
MENU_LOAD_DELAY = 2  # delay for menu loading
BRAKE_DURATION = 0.2  # duration for brake press in farming mode

# === Conversion Constants ===
MS_TO_KMH = 3.6  # m/s to km/h conversion factor
W_TO_KW = 1000.0  # watts to kilowatts conversion

# === Shifting Thresholds ===
SPEED_THRESHOLD = 0.1  # minimum speed (m/s) to record data or shift
MAX_SLIP_RATIO = 1.1  # maximum slip ratio cap
DOWNSHIFT_SPEED_FACTOR = 0.95  # downshift trigger: speed < target * factor
RESET_DRIVING_LINE_THRESHOLD = 127  # driving line threshold for reset detection
RESET_MIN_SPEED = 20  # minimum speed for reset detection
RESET_COUNT_THRESHOLD = 100  # reset car counter threshold
RESET_COOLDOWN_SECONDS = 10  # reset cooldown in seconds
FARMING_BRAKE_INTERVAL = 30  # AFK brake interval in seconds
TCS_SLIP_THRESHOLD = 0.5
TCS_MIN_SPEED = 5.0
TCS_THROTTLE_REDUCTION = 0.3
TCS_ENABLED = True
GUI_REFRESH_INTERVAL = 0.016  # GUI refresh interval in seconds (~60Hz)
UDP_BUFFER_SIZE = 1024  # UDP receive buffer size

# === Project URLs ===
GITHUB_URL = 'https://github.com/Burlesque1/Horizon6AutoGear'

# === Paths ===
CONFIG_DIR_NAME = 'config'
LOG_DIR_NAME = 'log'
EXAMPLE_DIR_NAME = 'data/cars'

# === Gear Shift Algorithm ===
GEAR_RATIO_WINDOW_SIZE = 20  # sliding window size for gear ratio smoothing
GEAR_RATIO_WINDOW_STEP = 5  # step size for sliding window
SHIFT_POINT_RPM_STEP = 50  # RPM step for optimal shift point search
RWD_LOW_GEAR_THRESHOLD = 3  # RWD cars: adjust shifting below this gear
SPEED_DIFF_WARNING_THRESHOLD = 0.1  # 10% speed gap triggers warning
TORQUE_BIN_RPM_STEP = 100  # RPM bin width for torque curve smoothing

# === Threading ===
MAX_WORKER_THREADS = 8
THREAD_NAME_PREFIX = "exec"

# === Forza Data Constants ===
FORZA_INPUT_MAX = 255  # max byte value for throttle/brake input
UDP_SOCKET_TIMEOUT = 1.0  # UDP socket timeout in seconds

# === Logger Settings ===
LOGGER_NAME = 'Horizon6AutoGear'
LOG_FILENAME = 'horizon6_autogear.log'
LOG_FILE_MODE = 'w'
LOG_LINE_LIMIT = 200
LOG_LINE_CHECK = 250

# === Default Car Properties ===
DEFAULT_MIN_GEAR = 1
DEFAULT_MAX_GEAR = 10

# === GUI Settings ===
WINDOW_TITLE = "Horizon 6: Auto Gear Shifting"
WINDOW_GEOMETRY = "1300x800"
WINDOW_MIN_SIZE = (1200, 800)
TIRE_SLIP_GREEN_THRESHOLD = 0.8  # below this = green zone
TIRE_SLIP_RED_RANGE = 0.2  # range for red zone calculation
# === Recording ===
RECORDING_DIR_NAME = 'data/recordings'
RECORDING_FILE_EXTENSION = '.f6rec.json'

# === Coach HUD ===
COACH_DL_GREEN_THRESHOLD = 0.25    # |normalized| < this = on line (green)
COACH_DL_YELLOW_THRESHOLD = 0.6    # < this = moderate deviation (yellow)
COACH_BRAKE_GREEN_THRESHOLD = 0      # raw diff >= this = OK (green)
COACH_BRAKE_YELLOW_THRESHOLD = -80   # raw diff >= this = approaching (yellow)
COACH_TIRE_SLIP_GREEN = 0.5        # combined_slip < this = good grip
COACH_TIRE_SLIP_YELLOW = 0.8       # combined_slip < this = approaching limit
COACH_HUD_WIDTH = 600
COACH_HUD_HEIGHT = 80
COACH_HUD_ALPHA = 0.85             # overlay transparency (0.0-1.0)

SEMI_AUTO_BRAKE_ANTICIPATION_HEAVY = 80.0
SEMI_AUTO_BRAKE_ANTICIPATION_MEDIUM = 60.0
SEMI_AUTO_BRAKE_ANTICIPATION_LIGHT = 50.0
PID_BRAKE_KP = 0.5
PID_BRAKE_KI = 0.05
PID_BRAKE_KD = 0.1
PID_INTEGRAL_LIMIT = 2.0
BRAKE_RELEASE_HYSTERESIS = 0.98

SETTINGS_WIDGET_START_Y = 0.03
SETTINGS_WIDGET_SPACING = 0.05
CAR_PERF_Y_OFFSET = 0.28  # vertical offset from CAR_INFO_TOPBOUND_RELY
PERF_STICKER_WIDTH = 0.12
PERF_STICKER_HEIGHT = 0.06
PERF_INDEX_WIDTH = 0.064
PERF_INDEX_HEIGHT = 0.05

# === WebSocket / Debug Server ===
WEBSOCKET_DEFAULT_PORT = 8765
BROADCAST_HZ = 30  # telemetry broadcast frequency
AGENT_PING_INTERVAL = 10  # seconds between agent pings

# === Gear Shift Settings ===
SHIFT_FACTOR = 0.97
OFFROAD_RALLY_SHIFT_FACTOR = 0.93

# === Text Settings ===
SELECT_LANGUAGE_TXT = ['Select Language:', '选择语言:']
LANGUAGE_TXT = ['English', '中文']
DEFAULT_LANG_INDEX = 0

CLUTCH_SHORTCUT_TXT = ['Clutch Shortcut:', '离合快捷键:']
UPSHIFT_SHORTCUT_TXT = ['Upshift Shortcut:', '升档快捷键:']
DOWNSHIFT_SHORTCUT_TXT = ['Downshift Shortcut:', '降档快捷键:']
CLUTCH_TXT = ['Enable Clutch', '开启离合']
FARM_TXT = ['Enable Farm', '开启刷图']
OFFROAD_RALLY_TXT = ['Offroad, Rally', '越野，拉力']
CAR_ID = ['Car ID:', '车辆序号:']
CAR_CLASS = ['Car Class:', '车辆等级:']
CAR_PERF = ['Car Performance:', '车辆性能:']
CAR_DRIVETRAIN = ['Car Drivetrain:', '车辆传动:']
TIRE_INFORMATION_TXT = ['Tire Information', '轮胎信息']
ACCEL_TXT = ['Acceleration', '加速']
BRAKE_TXT = ['Brake', '刹车']
SHIFT_POINT_TXT = ['Shift Point', '换挡点']
TREE_VALUE_TXT = ['Value', '结果']
SPEED_TXT = ['Speed', '速度']
RPM_TXT = ['RPM', '转速']
COLLECT_BUTTON_TXT = ['Collect Data', '收集数据']
ANALYSIS_BUTTON_TXT = ['Analysis', '分析数据']
RUN_BUTTON_TXT = ['Auto', '自动换挡']
OBSERVE_BUTTON_TXT = ['Observe', '纯显示']
PAUSE_BUTTON_TXT = ['Pause', '暂停']
EXIT_BUTTON_TXT = ['Exit', '退出']
CLEAR_LOG_TXT = ['Clear', '清空']
RECORD_TXT = ['Record', '录制']
PLAYBACK_TXT = ['Playback', '回放']
STOP_RECORD_TXT = ['Stop Rec', '停止录制']
STOP_PLAYBACK_TXT = ['Stop Play', '停止回放']
LIVE_TORQUE_TAB_TXT = ['Live Torque', '实时扭矩']
COACH_MODE_TXT = ['Coach', '教练']
TCS_LABEL = ['TCS', '牵引力控制']

BOOST_TXT = ['Boost', '增压']
FUEL_TXT = ['Fuel', '燃油']
GEAR_TXT = ['Gear', '档位']
THROTTLE_TXT = ['Throttle', '油门']
POWER_TXT = ['Power', '功率']
TORQUE_TXT = ['Torque', '扭矩']
LAP_TXT = ['Lap', '圈数']
BEST_LAP_TXT = ['Best', '最快']
LAST_LAP_TXT = ['Last', '上一圈']
CUR_LAP_TXT = ['Current', '当前圈']
RACE_POS_TXT = ['Pos', '名次']
RACE_TIME_TXT = ['Race', '比赛']
PITCH_TXT = ['Pitch', '俯仰']
ROLL_TXT = ['Roll', '侧倾']
STEER_TXT = ['Steer', '转向']
DIST_TXT = ['Dist', '距离']
CONNECTION_TXT = ['Connection', '连接']
DISPLAY_THEME_TXT = ['Display Theme', '显示主题']
SUSP_TRAVEL_TXT = ['Susp Travel', '悬挂行程']
LOG_TAB_TXT = ['Log', '日志']
CHARTS_TAB_TXT = ['Charts', '图表']
SHIFT_POINTS_TAB_TXT = ['Shift Points', '换挡点']
CONFIRM_TXT = ['Confirm', '确认']
SETTINGS_TITLE = ['Settings', '设置']
CAR_CLASS_TXT = ['Car Class', '车辆等级']

PROGRAM_INFO_TXT = [
    f'Horizon6AutoGear v2.0\nGlass Edition\n\n'
    f'Real-time telemetry display with live power curves, G-force diagram, and tire temperature monitoring.\n\n'
    f'Protocol: {PACKET_FORMAT.upper()}\nRefresh: {int(1/GUI_REFRESH_INTERVAL)} Hz\n\n'
    f'GitHub: {GITHUB_URL}',
    f'Horizon6AutoGear v2.0\nGlass Edition\n\n'
    f'实时遥测显示，包含功率曲线、G力图和轮胎温度监控。\n\n'
    f'协议: {PACKET_FORMAT.upper()}\n刷新率: {int(1/GUI_REFRESH_INTERVAL)} Hz\n\n'
    f'GitHub: {GITHUB_URL}',
]
