import xmlrunner
import unittest
import os
import argparse


def test_runner(file, verbosity=2, default_filter="testcase"):
    """
    Test runner core
    :param file: Full path to caller file
    :param verbosity: Verbosity level of unittest runner (0- quiet, 2 - verbose)
    :param default_filter: Test case filter that must be fulfilled to apply custom filter
    :return: None
    """
    # Get arguments
    parser = argparse.ArgumentParser(
        prog=f'test_runner',
        description=f'Runner for unittest test case',)
    parser.add_argument('--iter', required=False, metavar='I', help='Number of test iterations')
    parser.add_argument('--noxml', help='Use test report instead of default XML report', action='store_true')
    parser.add_argument('--cases', help='List of test cases filters to apply to current directory files', nargs='+')
    (args, _) = parser.parse_known_args()

    results = None

    if args.iter is None:
        args.iter = 1

    if args.cases is None:
        args.cases = []

    # Directory of caller file
    directory = os.path.dirname(file)

    # Run tests for given number of iterations
    for i in range(int(args.iter)):

        # Load tests into test suite
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()

        # No argument specified, run all TestCases that are imported into parent file
        if len(args.cases) != 0:
            # List all files in current directory
            files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))
                     and f.endswith('py')]
            test_files = []

            # Use only files that comply with filter
            for fltr in args.cases:
                for f in files:
                    if fltr.lower() in f.lower() and default_filter.lower() in f.lower():
                        test_files.append(f)

            # For all test case files
            for f in test_files:
                suite.addTests(loader.discover(directory, f))

        if args.noxml is None:
            runner = xmlrunner.XMLTestRunner(output='test-reports', verbosity=verbosity,
                                             failfast=False, buffer=False)
        else:
            runner = unittest.TextTestRunner(verbosity=verbosity)

        # Run either created suite or run Main to discover all testcases
        if len(args.cases):
            results = runner.run(suite)
        else:
            results = unittest.main(testRunner=runner, argv=[file], catchbreak=False, exit=False).result

    return results
