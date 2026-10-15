import logging
import os
import datetime as dt


class LastRecordHandler(logging.Handler):
    """
    Class that implements buffer for last X logging messages
    """
    MAX_COUNT = 7

    def __init__(self):
        """
        Initialize logging handler and clear all records
        """
        logging.Handler.__init__(self)
        self.records = []

    def emit(self, record):
        """
        Append emitted record to list of the most recent messages
        :param record: Current record
        :return: None
        """
        self.records.append(record)
        if len(self.records) > self.MAX_COUNT:
            self.records.pop(0)

    def get_record(self):
        """
        Retrieve the status message of last X records
        :return: String message of the X most recent records
        """
        ret = "STATUS WINDOW \n(from oldest to newest)"
        for rec in self.records:
            ret += '\n\n' + rec.asctime + ' - ' + rec.getMessage()
        return ret

    def get_one_liner(self):
        """
        Retrieve only the last record
        :return: String message with one most recent record
        """
        rec = self.records[-1]
        return rec.asctime + ' - ' + rec.getMessage()


class AppLogging:
    """
    Logging class that keeps recent messages for the status window and optionally stores them into log file
    """
    LOG_DIRECTORY = 'log/'
    FILE_NAME = dt.datetime.now().strftime("%Y-%m-%d-%H-%M.log")
    #: Default of logging into file for new instances (disabled, enable by enable_file() or file=True)
    FILE_ENABLED = False

    def __init__(self, level=logging.INFO, file=None):
        """
        Set all loggers and formatter, optionally create new log file
        :param level: Default logging level
        :param file: True to log into file, False not to, None to use class default FILE_ENABLED
        """
        self.level = level
        self.fh = None

        # Formatter for logging into file and console
        logger = logging.getLogger()
        logger.setLevel(level)
        self.formatter = logging.Formatter('%(asctime)-15s %(levelname)-8s %(module)s:%(lineno)s - %(message)s')
        ch = logging.StreamHandler()
        ch.setLevel(logging.ERROR)
        ch.setFormatter(self.formatter)
        logger.addHandler(ch)
        self.lrl = LastRecordHandler()
        logger.addHandler(self.lrl)

        if self.FILE_ENABLED if file is None else file:
            self.enable_file()

        self.log = logging.getLogger()
        self.log.info('Application started')

        self.head = []
        self.values = []

    def enable_file(self, enable=True, directory=None):
        """
        Enable or disable logging into file
        :param enable: True to enable, False to disable logging into file
        :param directory: Directory of log files, default LOG_DIRECTORY
        :return: None
        """
        logger = logging.getLogger()
        if self.fh is not None:
            logger.removeHandler(self.fh)
            self.fh.close()
            self.fh = None
        if not enable:
            return
        directory = self.LOG_DIRECTORY if directory is None else directory
        if not os.path.exists(directory):
            os.makedirs(directory)
        self.fh = logging.FileHandler(os.path.join(directory, self.FILE_NAME))
        self.fh.setLevel(self.level)
        self.fh.setFormatter(self.formatter)
        logger.addHandler(self.fh)

    def report_add(self, head, value):
        """
        Add new value into report table
        :param head: Heading of the table column
        :param value: Value
        :return: None
        """
        self.head.append(head)
        self.values.append(value)

    def write_report(self, name):
        """
        Write accumulated report into file - append
        :param name: Name of the file
        :return: None
        """
        if not os.path.exists(self.LOG_DIRECTORY):
            os.makedirs(self.LOG_DIRECTORY)
        line = ' | '.join(map(str, self.values))
        with open(self.LOG_DIRECTORY + '/' + name, 'a+', encoding='utf-8-sig') as f:
            f.seek(0, 2)
            val = f.tell()
            if val == 0:
                header = ' | '.join(map(str, self.head))
                f.write('| ' + header + ' |\n')
            f.write('| ' + line + ' |\n')
            f.close()


