# Third-party
import numpy as np

# Local
import horizon6_autogear.config.config as constants
from horizon6_autogear.core.car_info import CarInfo

# === Optimal Shift Point ===
# speed = rpm * 60 * (dia of tire * PI ) / gear ratio / other ratio
# dia of tire, other ratio and PI are constants, said C. So we have:
# speed = C * rpm * / gear ratio / other ratio, where the gR is the 1/ (gear ratio * other ratio)
# speed = rpm * gR (gear ratio), where the gR is the 1/ (gear ratio * other ratio * C)
# The best shift point is using: https://glennmessersmith.com/shiftpt.html
#
# Now we want to shift from Gear G1 to Gear G2 (continued) at r (rpm), the gear ratio is gR1 and gR2 while at G1 and G2.
# Let's said getTorque(r) return the Torque while rpm is r.
# We have: delta = getTorque(r) / gR1 - getTorque(r / gR2 * gR1) / gR2
# The goal is to make sure the delta is closed to 0. Then the r is the optimal shift point, said rpmo.
# We cannot get the gR1 or gR2 directly but we know we could get C * gR from speed / rpm, said S/R, while at Gear G.
# Then we could calculate gRn at Gn by (Sn / Rn), said gR(G) is the ration at Gear G
# Meanwhile the C is a constant and could be combined with gR. We have:
# delta(r, G) = getTorque(r) / gR(G) - getTorque(r / gR(G + 1) * gR(G)) / gR(G + 1)
# and delta(r, G) -> 0


def set_car_properties(records: dict, forza: CarInfo):
    """set car properties before running

    Args:
        records (dict): records
        forza ([type]): forza
    """
    gears = np.array([item['gear'] for item in records])
    gear_list = np.unique(gears)
    forza.minGear = gear_list.min()
    forza.maxGear = gear_list.max()


def get_rpm_torque_map(records: dict, forza: CarInfo):
    """get mapping from rpm to torque

    Args:
        records (dict): records
        forza ([type]): forza

    Returns:
        dict: mapping from rpm to torque on each gear
    """
    res = {}

    # find rpm range
    for g in records.keys():
        torques = np.array([item['torque'] for item in records[g]])

        # find the largest stable range that torque > 0
        torque_indices = np.where(torques < 0)[0]
        length = -1
        min_rpm_index = 0
        max_rpm_index = len(torques) - 1
        for i in range(len(torque_indices)):
            if torque_indices[i] == 0:
                continue

            if i == 0 and torque_indices[i] > 0:
                length = torque_indices[i]
                min_rpm_index = 0
                max_rpm_index = torque_indices[i] - 1
            elif i == len(torque_indices) - 1 and torque_indices[i] < len(torques) - 1:
                tmp_len = len(torques) - torque_indices[i] - 1
                if tmp_len > length:
                    length = tmp_len
                    min_rpm_index = torque_indices[i] + 1
                    max_rpm_index = len(torques) - 1
            else:
                tmp_len = torque_indices[i] - torque_indices[i - 1] - 1
                if tmp_len > length:
                    length = tmp_len
                    min_rpm_index = torque_indices[i - 1] + 1
                    max_rpm_index = torque_indices[i] - 1

        res[g] = {'min_rpm_index': min_rpm_index, 'max_rpm_index': max_rpm_index}

        lower_rpm = records[g][min_rpm_index]['rpm']
        upper_rpm = records[g][max_rpm_index]['rpm']
        forza.logger.debug(f'[Analyze] Gear {g}: RPM range {lower_rpm:.0f} ~ {upper_rpm:.0f} ({max_rpm_index - min_rpm_index} samples)')
    return res


def get_gear_ratio_map(records: dict, forza):
    """get gear ratio on each gear

    Args:
        records (dict): records

    Returns:
        [dict]: gear ratio on each gear
    """
    res = {}

    for gear, items in records.items():
        var = float('inf')
        ratio = -1
        for index in range(0, len(items) - constants.GEAR_RATIO_WINDOW_SIZE, constants.GEAR_RATIO_WINDOW_STEP):
            t = items[index:index + constants.GEAR_RATIO_WINDOW_SIZE]
            ratios = [item['speed/rpm'] for item in t]
            tmp_var = np.var(ratios)
            if tmp_var < var:
                ratio = np.average(ratios)
                var = tmp_var

        forza.logger.debug(f'[Analyze] Gear {gear}: ratio={ratio:.4f}')
        res[gear] = {
            'ratio': ratio,
        }

    return res


def build_torque_curve(records: list, rpm_step: int):
    """Build smoothed RPM -> torque mapping by binning and averaging.

    Groups records into RPM bins of width rpm_step, averages positive torque
    values within each bin. Returns sorted arrays suitable for np.interp.
    Positive-torque filter is applied defensively -- input may or may not
    be pre-filtered by get_rpm_torque_map.

    Args:
        records (list): list of record dicts with 'rpm' and 'torque' keys
        rpm_step (int): RPM bin width

    Returns:
        (np.ndarray, np.ndarray): sorted RPM bin centers, average torque values
    """
    rpms = np.array([item['rpm'] for item in records])
    torques = np.array([item['torque'] for item in records])

    # Filter: only positive torque (engine braking is not useful data)
    pos_mask = torques > 0
    rpms = rpms[pos_mask]
    torques = torques[pos_mask]

    if len(rpms) == 0:
        return np.array([]), np.array([])

    # Bin by rpm_step, use median (robust to outlier frames from throttle lift-off)
    bin_indices = (rpms / rpm_step).astype(int)
    bin_rpms = []
    bin_torques = []
    for b in np.unique(bin_indices):
        mask = bin_indices == b
        vals = torques[mask]
        if len(vals) < 2:
            continue  # need at least 2 points for a reliable estimate
        bin_rpms.append(b * rpm_step + rpm_step / 2)
        bin_torques.append(np.median(vals))

    return np.array(bin_rpms), np.array(bin_torques)


def get_torque(r: float, curve_rpms: np.ndarray, curve_torques: np.ndarray):
    """Get smoothed torque at RPM r via linear interpolation.

    Args:
        r (float): target RPM
        curve_rpms (np.ndarray): sorted RPM bin centers from build_torque_curve
        curve_torques (np.ndarray): corresponding average torque values

    Returns:
        float: interpolated torque, or 0 if curve is empty
    """
    if len(curve_rpms) == 0:
        return 0
    return float(np.interp(r, curve_rpms, curve_torques))


def get_gear_ratio(g: int, gear_ratios: dict):
    """get gear ratio

    Args:
        g (int): gear
        gear_ratios (dict): mapping of gear to gear ratio

    Returns:
        [float]: gear ratio
    """
    return gear_ratios[g]['ratio']


def calculate_optimal_shift_point(forza: CarInfo):
    """calculate optimal shift points

    Args:
        forza (CarInfo): forza

    Returns:
        [dict]: optimal shift points
    """
    # result, (gear, record)
    res = {}

    # records by gears
    records_by_gears = {}
    for items in forza.records:
        if items['gear'] not in records_by_gears.keys():
            records_by_gears[items['gear']] = []
        records_by_gears[items['gear']].append(items)

    # set car properties
    set_car_properties(forza.records, forza)

    # get gear ratio
    forza.gear_ratios = get_gear_ratio_map(records_by_gears, forza)

    # search optimal rpm from gear G to gear G + 1
    forza.rpm_torque_map = get_rpm_torque_map(records_by_gears, forza)
    sorted_gears = sorted(forza.gear_ratios.keys())
    for i, gear in enumerate(sorted_gears):
        if i >= len(sorted_gears) - 1:
            break

        next_gear = sorted_gears[i + 1]
        rpm_torque = forza.rpm_torque_map[gear]
        rpm_torque1 = forza.rpm_torque_map[next_gear]
        rpm_to_torque = records_by_gears[gear][rpm_torque['min_rpm_index']:rpm_torque['max_rpm_index']]
        rpm_to_torque1 = records_by_gears[next_gear][rpm_torque1['min_rpm_index']:rpm_torque1['max_rpm_index']]

        ratio = forza.gear_ratios[gear]['ratio']
        ratio1 = get_gear_ratio(next_gear, forza.gear_ratios)

        # Build smoothed torque curves (bin + average)
        curve_rpms, curve_torques = build_torque_curve(rpm_to_torque, constants.TORQUE_BIN_RPM_STEP)
        curve_rpms1, curve_torques1 = build_torque_curve(rpm_to_torque1, constants.TORQUE_BIN_RPM_STEP)
        forza.logger.debug(f'[Analyze] Gear {gear}: {len(curve_rpms)} torque bins, Gear {next_gear}: {len(curve_rpms1)} torque bins')

        # search optimal rpm: find where delta crosses zero
        max_rpm = int(max(np.max(curve_rpms), np.max(curve_rpms1))) if len(curve_rpms) > 0 and len(curve_rpms1) > 0 else 0
        # Ensure G+1 query point (r * ratio / ratio1) stays within G+1's data range
        min_rpm = int(max(np.min(curve_rpms), np.min(curve_rpms1) * ratio1 / ratio)) if len(curve_rpms) > 0 and len(curve_rpms1) > 0 else 0

        if min_rpm >= max_rpm:
            # No valid overlap: shift at redline
            rpmo = max_rpm
            forza.logger.info(f'[Analyze] Gear {gear} -> {next_gear}: no overlap, redline optimal ({max_rpm} RPM)')
        else:
            rpmo = max_rpm
            prev_delta = None
            for r in range(max_rpm, min_rpm, -constants.SHIFT_POINT_RPM_STEP):
                # delta(r, G) = getTorque(r) / gR(G) - getTorque(r / gR(G + 1) * gR(G)) / gR(G + 1)
                torque = get_torque(r, curve_rpms, curve_torques) / ratio
                torque1 = get_torque(r / ratio1 * ratio, curve_rpms1, curve_torques1) / ratio1
                delta = torque - torque1

                if prev_delta is not None and prev_delta > 0 and delta <= 0:
                    # Delta crossed zero between r+STEP and r: interpolate
                    step = constants.SHIFT_POINT_RPM_STEP
                    rpmo = (r + step) - prev_delta / (delta - prev_delta) * step
                    break
                prev_delta = delta

        speedo = rpm_to_torque[np.abs(np.array([item['rpm'] for item in rpm_to_torque]) - rpmo).argmin()]['speed']
        theory_speed = rpmo * ratio
        # Diagnostic: Delta curve characteristic for verification
        delta_at_min = get_torque(min_rpm, curve_rpms, curve_torques) / ratio - get_torque(min_rpm * ratio / ratio1, curve_rpms1, curve_torques1) / ratio1
        delta_at_max = get_torque(max_rpm, curve_rpms, curve_torques) / ratio - get_torque(max_rpm * ratio / ratio1, curve_rpms1, curve_torques1) / ratio1
        cross = delta_at_max > 0 and delta_at_min < 0
        cross_desc = "crosses zero" if cross else "stays positive -> redline optimal"
        forza.logger.info(f'[Analyze] Gear {gear} -> {next_gear}: shift at {rpmo:.0f} RPM / {theory_speed:.1f} km/h (Delta: {delta_at_max:.0f} @ {max_rpm} -> {delta_at_min:.0f} @ {min_rpm}, {cross_desc})')
        speed_diff = 1 - min(speedo, theory_speed) / max(speedo, theory_speed)
        if speed_diff > constants.SPEED_DIFF_WARNING_THRESHOLD:
            forza.logger.warning(f'[Analyze] Gear {gear} ratio suspect: {speed_diff * 100:.1f}% speed gap (expected <10%). Re-collect data?')
        res[gear] = {'rpmo': rpmo, 'speed': theory_speed}

    return res



