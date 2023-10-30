import unittest
import os
from time import sleep

try:
    import lecore.TestFram.Runner as TR
except ImportError:
    import src.lecore.TestFrame.Runner as TR

# Import miscellaneous test cases
from test_looger import *
from test_fg320 import *


if __name__ == '__main__':
    # Get canonical path to this file (remove symlinks)
    file = os.path.realpath(__file__)

    # Run test runner
    TR.test_runner(file, default_filter='')
