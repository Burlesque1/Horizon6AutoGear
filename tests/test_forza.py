import os
import sys

sys.path.append(r'.')
sys.path.append(r'./src')  # Add src to path for package imports

from concurrent.futures import ThreadPoolExecutor

import horizon6_autogear.config.config as constants
import horizon6_autogear.core.forza as forza
import horizon6_autogear.utils.helper as helper

threadPool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="exec")
engine = forza.Forza(threadPool, packet_format=constants.PACKET_FORMAT, enable_clutch=constants.ENABLE_CLUTCH)


def test_analysis():
    helper.load_config(engine, os.path.join(constants.ROOT_PATH, 'tests', 'analysis_test.json'))
    engine.analyze(performance_profile=False, is_gui=False)

    # gear 1 => ( ] => torque is larger than 0 at the beginning, but has negative values at the end
    assert engine.rpm_torque_map[1]['min_rpm_index'] == 0
    assert engine.rpm_torque_map[1]['max_rpm_index'] == 141

    # gear 2 => ( ) => torque is larger than 0 all the time during the gear 2
    assert engine.rpm_torque_map[2]['min_rpm_index'] == 0
    assert engine.rpm_torque_map[2]['max_rpm_index'] == 143

    # gear 3 => [ ) => torque is less than 0 at the beginning but larger than 0 at the end
    assert engine.rpm_torque_map[3]['min_rpm_index'] == 9
    assert engine.rpm_torque_map[3]['max_rpm_index'] == 269

    # gear 4 => [ ] => torque is less than 0 at the beginning and the end
    assert engine.rpm_torque_map[4]['min_rpm_index'] == 9
    assert engine.rpm_torque_map[4]['max_rpm_index'] == 424

    # gear 5. Last => last gear
    assert engine.rpm_torque_map[5]['min_rpm_index'] == 9
    assert engine.rpm_torque_map[5]['max_rpm_index'] == 594
