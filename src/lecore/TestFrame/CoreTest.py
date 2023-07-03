import xmlrunner
import sys

from . import *


def core_test_run(unit_args, directory='./', verbosity=2):
    """
    Run test suites on given directory
    :param unit_args: String or int array of test numbers to run. If empty, it runs all test.
    :param directory: Directory for test discovery
    :param verbosity: Verbosity of unittest output
    :return: True on success, false when test suite cannot be found
    """
    # No argument specified, run all UnitTests
    if len(unit_args) == 0:
        test_runner = xmlrunner.XMLTestRunner(output='test-reports', verbosity=verbosity)
        unittest.main(testRunner=test_runner, argv=[sys.argv[0]],
                      failfast=False, buffer=False, catchbreak=False, exit=False)
    else:
        # argument to list of TestCases
        int_args = list(map(int, unit_args))
        test_suites = list(map(lambda a: 'testsuite{:03}'.format(a), int_args))

        files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
        test_files = []
        for f in files:
            if f.lower().endswith('.py') and f.lower().startswith(tuple(test_suites)):
                test_files.append(f)

        for test_case in test_files:
            logger.info(test_case)
            root_dir = directory
            loader = unittest.TestLoader()
            suite = loader.discover(root_dir, test_case)
            check = suite.countTestCases()
            if check == 0:
                logger.error("TestCase <{}> not found!".format(test_case))
                return False

            runner = xmlrunner.XMLTestRunner(output='test-reports', verbosity=verbosity)
            results = runner.run(suite)
            logger.info("results: %s" % results)
            logger.info("results.wasSuccessful: %s" % results.wasSuccessful())

    return True

