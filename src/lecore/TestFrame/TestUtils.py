import logging
import os
import sys
import io
import datetime
import struct

# Set level for default logger
log_def = logging.getLogger()
log_def.setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s  %(levelname)-8s  %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
# create console handler
ch = logging.StreamHandler()
ch.setFormatter(formatter)
# add the handlers to logger
logger.addHandler(ch)

# Create file handler
log_filename = datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '.txt'
path_to_log_directory = './Log/'

# Create directory if not exist
if not os.path.exists(path_to_log_directory):
    os.makedirs(path_to_log_directory)

fh = logging.FileHandler(filename=os.path.join(path_to_log_directory, log_filename))
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)


def is_testing_platform(switch='linux'):
    """
    Is it a testing linux platform
    :param switch: Name of operating system of testing platform
    :return: True on match
    """
    if sys.platform.startswith(switch):
        return True
    else:
        return False


def get_firmware_version(file_name, offset):
    """
    Get firmware version from binary file
    :param file_name: Name of binary file
    :param offset: Offset of version id in bytes
    :return: Firmware version
    """
    with io.open(file_name, 'rb') as f:
        content = f.read(offset + 4)
    return struct.unpack('<L', content[offset:])[0]


def util_setup(self):
    """
    Print information about test case into logger at INFO level
    :param self: testCase class object
    :return: None
    """
    logger.info('                            ')
    suite = self.id().split('.')[-2]
    case = self.id().split('.')[-1]
    logger.info('********   < {} ({}) >   **********'.format(suite, case))


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

