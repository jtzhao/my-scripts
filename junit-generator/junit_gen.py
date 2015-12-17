#!/usr/bin/env python2
# -*- coding: UTF-8 -*-
import datetime
import fnmatch
import glob
import json
import logging
import os
from optparse import OptionParser
import re
import subprocess

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET


# Read <count> lines from a file with a specific encoding(default: utf-8).
# Return a unicode object.
def read_with_encoding(path, encoding='utf-8', count=None):
    # Expand path
    path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    path = os.path.abspath(path)
    # Read file line by line
    lines = []
    if not os.access(path, os.R_OK):
        return None
    with file(path, 'rb') as f:
        for line in f:
            line = line.strip()
            lines.append(line)
            if isinstance(count, int):
                count -= 1
                if count <= 0:
                    break
    return unicode('\n'.join(lines), encoding)


class ResultFileParser(object):
    '''
    Parse one test_results file to a dict

    Test result file format:
        <test_name>
        <fail> <succeed> <count> <time> <error> <skipped>
    '''
    RESULT_ITEMS = ['failed', 'succeeded', 'count', 'time', 'error', 'skipped']

    #   path: Path to the test_results file
    def __init__(self, path, logger=None):
        if logger is None:
            self.logger = logging.getLogger(self.__class__.__name__)
        else:
            self.logger = logger
        self.testcases = []
        self.path = path

    # Read and parse the test_results file
    # and save the result to self.testcases
    def parse(self):
        testcase_name = ''
        line_num = 0
        self.logger.debug("Parsing file %s" % (self.path))
        with file(self.path, 'r') as f:
            # Parse test_results file line by line
            for line in f:
                line_num += 1
                line = line.strip()
                # Testcase name line
                if line_num % 2 == 1:
                    testcase_name = line
                    self.logger.debug("Parsing testcase %s" % (testcase_name))
                    assert len(testcase_name) != 0, "Invalid format(%s:%s)" % (self.path, line_num)
                    continue
                # Test result line
                self.logger.debug("Getting results of testcase %s" % (testcase_name))
                states = line.split()
                assert len(states) == 6, "Invalid format(%s:%s)" % (self.path, line_num)
                # Convert to int
                try:
                    states = map(int, states)
                except ValueError, e:
                    raise ValueError("ctcs2 test results must be integers(%s:%s)" % (self.path, line_num))
                # Save test result to self.testcases
                d = {'name': testcase_name}
                for i in range(len(self.RESULT_ITEMS)):
                    key = self.RESULT_ITEMS[i]
                    value = states[i]
                    d[key] = value
                d['log_file'] = os.path.join(os.path.dirname(self.path), testcase_name)
                self.testcases.append(d)
                # Reset testcase name
                testcase_name = ''
        assert line_num % 2 == 0, ("No test result of testcase '%s'(%s:%s)" %
                                (testcase_name, self.path, line_num))
        return self.testcases


class TestsuitesParser(object):
    '''
    Parse a tarball or dir containing test result dirs.

    Example:
        /var/log/qaset/log/gzip-ACAP2-20151216-20151216T110220.tar.bz2
        /var/log/qa/oldlogs
    '''

    RESULT_FILE_NAME    = 'test_results'
    TARBALL_PATTERN     = '*.tar.*'
    TMP_DIR             = '/tmp'

    # log_dir: The directory containing log tarballs or log dirs.
    def __init__(self, log_dir, logger=None):
        if logger is None:
            self.logger = logging.getLogger(self.__class__.__name__)
        else:
            self.logger = logger
        log_dir = os.path.expanduser(log_dir)
        log_dir = os.path.expandvars(log_dir)
        log_dir = os.path.abspath(log_dir)
        self.path = log_dir
        self.testsuites = []
        self.extraction_dir = None

    # Create extraction dir for extracting tarballs
    def mk_extraction_dir(self):
        self.TMP_DIR = '/tmp'
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        extraction_dir = os.path.join(self.TMP_DIR,
                        "testsuite-log-parser_%s" % (timestamp))
        try:
            os.mkdir(extraction_dir, 0755)
        except OSError, e:
            raise OSError("Dir %s already exists: %s" % (extraction_dir, e))
        except IOError, e:
            raise IOError("Failed to create %s for extraction: %s" % (extraction_dir, e))
        self.extraction_dir = extraction_dir
        return extraction_dir

    # Extract a tarball to self.extraction_dir
    # tarball: The path to the log tarball
    def extract(self, tarball):
        cmd = "tar xf '%s' -C '%s'" % (tarball, self.extraction_dir)
        ret = subprocess.call(cmd, shell=True)
        assert ret == 0, "Extraction failed: %s" % (cmd)

    # Get testsuite info from test log dir
    # entry: Path to the test log dir(e.g. /var/log/qaset/log/qa_gzip-2015-12-16-11-02-03)
    # info: name/timestamp
    def get_testsuite_info(self, entry, info):
        if info not in ['name', 'timestamp']:
            raise ValueError("Info type not supported: %s" % (info))
        entry = os.path.basename(entry)
        m = re.search(r'(.*)-(\d+(?:-\d+){5})', entry)
        if m is None:
            return None
        if info == 'name':
            return m.group(1)
        else:
            date_time_lst = m.group(2).split('-')
            date = '-'.join(date_time_lst[:3])
            time = ':'.join(date_time_lst[-3:])
            return "%s %s" % (date, time)

    # Get testsuite name from test log dir name
    def get_testsuite_name(self, entry):
        return self.get_testsuite_info(entry, 'name')

    # Get testsuite timestamp from test log dir name
    def get_testsuite_timestamp(self, entry):
        return self.get_testsuite_info(entry, 'timestamp')

    # Parse all the tarballs or dirs in self.path
    def parse(self):
        test_result_dirs = []
        self.mk_extraction_dir()
        # Handle each entry in log_dir
        print self.path
        for entry in glob.glob(os.path.join(self.path, '*')):
            # Log tarball
            if fnmatch.fnmatch(os.path.basename(entry), '*.tar.*'):
                try:
                    self.logger.debug("Extracting %s" % (entry))
                    self.extract(entry)
                except AssertionError, e:
                    self.logger.warning("Failed to extract %s. Skipping..." % (entry))
            # Log dir
            elif os.isdir(entry):
                test_result_dirs.append(entry)
            else:
                self.logger.warning("Unknown entry '%s'. Skipping..." % (entry))
        # Handle extracted entries
        test_result_dirs.extend(glob.glob(os.path.join(self.extraction_dir, '*')))
        # Parse each dir
        for entry in test_result_dirs:
            result_file = os.path.join(entry, self.RESULT_FILE_NAME)
            if not os.access(result_file, os.R_OK):
                self.logger.error("Failed to read test result: %s" % (result_file))
                continue
            # Create ResultFileParser for each file
            testsuite = {}
            result_parser = ResultFileParser(result_file, self.logger)
            try:
                testsuite['testcases'] = result_parser.parse()
            except Exception, e:
                self.logger.error("Failed to parse %s: %s" % (result_file, e))
                continue
            testsuite['name'] = self.get_testsuite_name(entry)
            testsuite['timestamp'] = self.get_testsuite_timestamp(entry)
            self.testsuites.append(testsuite)
        return self.testsuites


class Result2Junit(object):
    def __init__(self):
        pass


if __name__ == '__main__':
    logging.basicConfig(format='[%(name)s]%(levelname)s: %(message)s')
    logger = logging.getLogger('junit_gen')
    logger.setLevel(logging.DEBUG)

    read_with_encoding('~/a.txt')

    #parser = TestsuitesParser('~/log', logger)
    #data = parser.parse()
    #print json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '))
