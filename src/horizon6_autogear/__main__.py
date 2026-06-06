# Standard library
import argparse
import os
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor

# Add project root to Python path for new module structure
# __file__ is in src/horizon6_autogear/__main__.py, so go up 2 levels to reach project root
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Add src to path to import horizon6_autogear as a package
src_dir = os.path.join(project_root, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Third-party
from pynput.keyboard import Listener  # noqa: E402

# Local
import horizon6_autogear  # noqa: E402
import horizon6_autogear.config.config as constants  # noqa: E402
import horizon6_autogear.core.forza as forza  # noqa: E402
import horizon6_autogear.utils.helper as helper  # noqa: E402

# suppress matplotlib warning while running in threads
warnings.filterwarnings("ignore", category=UserWarning)

# Parse command line arguments
parser = argparse.ArgumentParser(
    description='Horizon6AutoGear - Automatic gear shifting for Forza Horizon 5',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Keyboard Shortcuts:
  F1   Switch to live tab
  F2   Collect gear data
  F3   Analyze collected data
  F4   Start/Stop auto shifting
  F5   Toggle recording
  F6   Observe mode (no shifting)
  F9   Stop the program
  F12  Exit the program

    """
)
parser.add_argument('--version', action='version', version=f'%(prog)s {horizon6_autogear.__version__}')
parser.add_argument('--test', action='store_true', help='Run in test mode (for development)')
args = parser.parse_args()

threadPool = ThreadPoolExecutor(max_workers=constants.MAX_WORKER_THREADS, thread_name_prefix=constants.THREAD_NAME_PREFIX)
engine = forza.Forza(threadPool, packet_format=constants.PACKET_FORMAT, enable_clutch=constants.ENABLE_CLUTCH)


def press_collect_data():
    """press collect data button
    """
    if engine.isRunning:
        engine.logger.info('stopping gear test')

        def stopping():
            engine.isRunning = False

        threadPool.submit(stopping)
    else:
        engine.logger.info('starting gear test')

        def starting():
            engine.isRunning = True
            engine.test_gear()

        threadPool.submit(starting)


def press_analysis():
    """press analysis button
    """
    if len(engine.records) <= 0:
        engine.logger.info(f'load config {constants.EXAMPLE_CAR_ORDINAL}.json for analysis as an example')
        helper.load_config(engine, os.path.join(constants.ROOT_PATH, constants.EXAMPLE_DIR_NAME, f'{constants.EXAMPLE_CAR_ORDINAL}.json'))
    engine.logger.info('Analysis')
    threadPool.submit(engine.analyze)


def press_auto_shift():
    """press auto shift button
    """
    if engine.isRunning:
        engine.logger.info('stopping auto gear')

        def stopping():
            engine.isRunning = False

        threadPool.submit(stopping)
    else:
        engine.logger.info('starting auto gear')

        def starting():
            engine.isRunning = True
            engine.run()

        threadPool.submit(starting)


def on_press(key):
    """on press callback

    Args:
        key: key
    """
    try:
        if key == constants.COLLECT_DATA:
            press_collect_data()
        elif key == constants.ANALYSIS:
            press_analysis()
        elif key == constants.AUTO_SHIFT:
            press_auto_shift()
        elif key == constants.STOP:
            engine.isRunning = False
            engine.logger.info('stopped')
        elif key == constants.CLOSE:
            engine.isRunning = False
            threadPool.shutdown(wait=False)
            engine.logger.info('bye~')
            exit()
    except Exception as e:
        engine.logger.exception(e)


def main():
    """Main entry point for CLI launcher and pyproject.toml."""
    try:
        engine.logger.info('Horizon6AutoGear Shifting Started!!!')
        with Listener(on_press=on_press) as listener:
            listener.join()
    finally:
        engine.isRunning = False
        threadPool.shutdown(wait=False)
        engine.logger.info('Horizon6AutoGear Shifting Ended!!!')


if __name__ == "__main__":
    main()
