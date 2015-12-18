#!/usr/bin/env python2
# -*- coding: UTF-8 -*-
import datetime
import fnmatch
import glob
import json
import logging
import os
from optparse import OptionParser
import random
import re
import shutil
import subprocess
import uuid

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET



class BaseParser(object):
    '''Base class of parser classes'''
    def __init__(self, logger=None):
        if logger is None:
            self.logger = logging.getLogger(self.__class__.__name__)
        else:
            self.logger = logger

    # Expand ~ and env vars of a path and return its absolute path
    def expand_path(self, path):
        path = os.path.expanduser(path)
        path = os.path.expandvars(path)
        path = os.path.abspath(path)
        return path
    
    # Read the last <count> lines from a file
    # with a specific encoding(default: utf-8).
    # Return a unicode object.
    def read_with_encoding(self, path, encoding='utf-8', count=100, newline='\n'):
        path = self.expand_path(path)
        if not os.access(path, os.R_OK):
            return None
        with file(path, 'rb') as f:
            lines = f.readlines()
        if isinstance(count, int):
            if count <= 0:
                raise ValueError("count must be larger than 0")
            lines = lines[-count:]
        # Remove the trailing \r\n characters
        def _rstrip(string):
            return string.rstrip()
        lines = map(_rstrip, lines)
        return unicode(newline.join(lines), encoding)


class TestsuiteLogDir(BaseParser):
    '''
    Parse one test_results file to a dict

    Test result file format:
        <test_name>                                         # testcase name line
        <fail> <succeed> <count> <time> <error> <skipped>   # test result line
    '''
    RESULT_ITEMS = ['failed', 'succeeded', 'count', 'time', 'error', 'skipped']
    TEST_RESULTS = 'test_results'

    # path: Path to the log dir.
    # Example: /usr/share/qa/ctcs2/qa_bzip2-2015-12-18-11-37-53
    def __init__(self, path, logger=None):
        super(TestsuiteLogDir, self).__init__(logger)
        self.data = {'testsuite_name': None,
                    'timestamp': None,
                    'testcases': []}
        self.path = self.expand_path(path)              # path to the log dir
        self.basename = os.path.basename(self.path)     # name of the log dir
        self.test_results_file = os.path.join(self.path, self.TEST_RESULTS)

    # Parse dir name to get testsuite name and timestamp
    def parse_name_timestamp(self):
        m = re.search(r'(.*)-(\d+(?:-\d+){5})', self.basename)
        if m is None:
            return None
        self.data['testsuite_name'] = m.group(1)
        lst = m.group(2).split('-')
        date = '-'.join(lst[:3])
        time = ':'.join(lst[-3:])
        self.data['timestamp'] = "%s %s" % (date, time)
        return self.data['testsuite_name'], self.data['timestamp']

    # Parse test result line and return a dict.
    # A test result line contains 6 numbers:
    #   <fail> <succeed> <count> <time> <error> <skipped>
    def extract_result_line(self, line):
        if not re.search(r'\d+(\s+\d+){5}', line):
            raise ValueError("Invalid result line: %s" % (line))
        nums = map(int, line.split())
        result = {}
        for i in range(len(self.RESULT_ITEMS)):
            result[self.RESULT_ITEMS[i]] = nums[i]
        return result

    # Get testcase timestamp from its log
    def extract_testcase_timestamp(self, testcase_log):
        m = re.search(r'^(\w+ \w+ \d+ (?:\d+:){2}\d+ \w+ \d+):', testcase_log, re.MULTILINE)
        if m is None:
            return None
        try:
            d = datetime.datetime.strptime(m.group(1), '%a %b %d %H:%M:%S %Z %Y')
            timestamp = d.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError, e:
            timestamp = m.group(1)
        return timestamp

    # Read and parse the test_results file
    # and save the result to self.data['testcases']
    #               [{'name'      : <testcase name>,
    #               'failed'    : 0,
    #               'succeeded' : 2,
    #               'count'     : 2,
    #               'time'      : 10,
    #               'error'     : 0,
    #               'skipped'   : 0,
    #               'log'       : <100 lines of the log>}]
    def parse_testcases(self):
        self.data['testcases'] = []
        testcase_name = ''
        line_num = 0
        self.logger.debug("Parsing file %s" % (self.test_results_file))
        assert os.access(self.test_results_file, os.R_OK), "Failed to read %s" % (self.test_results_file)
        with file(self.test_results_file, 'r') as f:
            # Parse test_results file line by line
            for line in f:
                line_num += 1
                line = line.strip()
                # Testcase name line
                if line_num % 2 == 1:
                    testcase_name = line
                    self.logger.debug("Parsing testcase %s" % (testcase_name))
                    assert len(testcase_name) != 0, "Invalid format(%s:%s)" % (self.test_results_file, line_num)
                    continue
                # Test result line
                self.logger.debug("Getting results of testcase %s" % (testcase_name))
                try:
                    testcase = self.extract_result_line(line)
                except ValueError, e:
                    self.logger.error("Invalid test result line(%s:%s)" % (self.test_results_file, line_num))
                    raise e
                testcase['testcase_name'] = testcase_name
                log_file_path = os.path.join(os.path.dirname(self.test_results_file), testcase_name)
                testcase['log'] = self.read_with_encoding(log_file_path)
                testcase['timestamp'] = self.extract_testcase_timestamp(testcase['log'])
                self.data['testcases'].append(testcase)
                # Reset testcase name
                testcase_name = ''
        assert line_num % 2 == 0, ("No test result of testcase '%s'(%s:%s)" %
                                (testcase_name, self.test_results_file, line_num))
        return self.data['testcases']

    # Parse all the data.
    # Return:
    # { 'testcases': [{'name'      : <testcase name>,
    #               'failed'    : 0,
    #               'succeeded' : 2,
    #               'count'     : 2,
    #               'time'      : 10,
    #               'error'     : 0,
    #               'skipped'   : 0,
    #               'log'       : <100 lines of the log>}],
    #   'name': <testsuite_name>,
    #   'timestamp': <timestamp>    }
    def parse(self):
        self.parse_name_timestamp()
        self.parse_testcases()
        return self.data


class TestsuiteLogTarball(BaseParser):
    '''
    Extract and parse the logs inside a tarball.
    A tarball may contain multiple testsuite log dirs'''

    TMP_DIR = '/tmp'

    # path: Path to the tarball containing logs. Example:
    #       /usr/share/qaset/log/gzip-ACAP2-20151216-20151216T110220.tar.bz2
    def __init__(self, path, logger=None):
        super(TestsuiteLogTarball, self).__init__(logger)
        self.path = path
        self.extraction_dir = None
        self.data = []              # A list of testsuites

    # Create extraction dir for extracting tarballs
    def create_extraction_dir(self):
        unique_id = uuid.uuid4()
        dirname = "extracted_logs_%s" % (unique_id)
        extraction_dir = os.path.join(self.TMP_DIR, dirname)
        self.logger.debug("Creating %s" % (extraction_dir))
        try:
            os.mkdir(extraction_dir, 0755)
        except OSError, e:
            raise OSError("Dir %s already exists: %s" % (extraction_dir, e))
        except IOError, e:
            raise IOError("Failed to create %s for extraction: %s" % (extraction_dir, e))
        self.extraction_dir = extraction_dir
        return self.extraction_dir

    # Remove the extraction dir
    def remove_extraction_dir(self):
        try:
            shutil.rmtree(self.extraction_dir)
        except OSError, e:
            self.logger.warning("Unable to remove extraction dir %s.\nMaybe it's already removed?" % (self.extraction_dir))
        self.extraction_dir = None

    # Extract a tarball to self.extraction_dir
    # tarball: The path to the log tarball
    def extract(self):
        cmd = "tar xf '%s' -C '%s'" % (self.path, self.extraction_dir)
        ret = subprocess.call(cmd, shell=True)
        assert ret == 0, "Extraction failed: %s" % (cmd)

    def parse(self):
        self.create_extraction_dir()
        self.extract()
        for entry in glob.glob(os.path.join(self.extraction_dir, '*')):
            p = TestsuiteLogDir(entry, self.logger)
            try:
                testsuite = p.parse()
                self.data.append(testsuite)
            except Exception, e:
                self.logger.warning("Failed to parse %s. Skipping..." % (entry))
        self.remove_extraction_dir()
        # Check if there's any data
        if len(self.data) == 0:
            self.logger.warning("No log data in %s" % (self.path))
        return self.data


class LogsParser(BaseParser):
    '''
    Parse all the logs under a directory.

    Example:
        /var/log/qaset/log/
    '''

    RESULT_FILE_NAME    = 'test_results'
    TARBALL_PATTERN     = '*.tar.*'
    TMP_DIR             = '/tmp'

    # path: The directory containing log tarballs or log dirs.
    #   Example: /var/log/qaset/log/
    def __init__(self, path, logger=None):
        super(LogsParser, self).__init__(logger)
        self.path = path
        self.data = []          # A list of testsuites data

    # Parse all the tarballs or dirs in self.path
    def parse(self):
        self.data = []
        for entry in glob.glob(os.path.join(self.path, '*')):
            if fnmatch.fnmatch(os.path.basename(entry), '*.tar.*'):
                p = TestsuiteLogTarball(entry)
            elif os.path.isdir(entry):
                p = TestsuiteLogDir(entry)
            else:
                self.logger.warning("Unknown entry '%s'. Skipping..." % (entry))
            try:
                p.parse()
            except Exception, e:
                self.logger.warning("Failed to parser %s. Skipping..." % (entry))
            if isinstance(p.data, list):
                self.data.extend(p.data)
            else:
                self.data.append(p.data)
        return self.data


class Result2Junit(object):
    def __init__(self):
        pass


if __name__ == '__main__':
    logging.basicConfig(format='[%(name)s]%(levelname)s: %(message)s')
    logger = logging.getLogger('junit_gen')
    logger.setLevel(logging.DEBUG)

    parser = LogsParser('/var/log/qaset/log')
    parser.parse()
    print json.dumps(parser.data, sort_keys=True, indent=4, separators=(',', ': '))

