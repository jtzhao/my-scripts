#!/usr/bin/env python2
# -*- coding: UTF-8 -*-
import datetime
import fnmatch
import glob
import logging
import os
from optparse import OptionParser

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET


class ResultFileParser(object):
    '''
    Parse one test_results file to a dict

    Test result file format:
        <test_name>
        <fail> <succeed> <count> <time> <error> <skipped>
    '''
    RESULT_ITEMS = ['fail', 'succeed', 'count', 'time', 'error', 'skipped']

    def __init__(self, path, logger=None):
        if logger is None:
            self.logger = logging.getLogger(self.__class__.__name__)
        else:
            self.logger = logger
        self.results = {}
        assert isinstance(path, basestring), "Given path is not a str"
        path = os.path.expanduser(path)
        path = os.path.expandvars(path)
        path = os.path.abspath(path)
        self.path = path

    def parse(self):
        testcase_name = ''
        line_num = 0
        with file(self.path, 'r') as f:
            # Parse test_results file line by line
            for line in f:
                line_num += 1
                line = line.strip()
                if line_num % 2 == 1:
                    # Testcase name
                    testcase_name = line
                    assert len(testcase_name) != 0, "%s:%s Invalid format" % (self.path, line_num)
                else:
                    # Test result
                    states = line.split()
                    assert len(states) == 6, "%s:%s Invalid format" % (self.path, line_num)
                    # Convert to int
                    try:
                        states = map(int, states)
                    except ValueError, e:
                        raise ValueError("%s:%s Failed to convert '%s' to int" % (self.path, line_num))
                    # Save test result to self.results
                    self.results[testcase_name] = {}
                    for i in range(len(self.RESULT_ITEMS)):
                        key = self.RESULT_ITEMS[i]
                        value = states[i]
                        self.results[testcase_name][key] = value
                    self.results[testcase_name]['log_file'] = os.path.join(os.path.dirname(self.path), key)
                    # Reset testcase name
                    testcase_name = ''
        assert line_num %2 == 0, ("%s:%s No test result of testcase '%s'" %
                                (self.path, line_num, testcase_name))
        return self.results


class TestsuiteLogParser(object):
    '''
    Parse a tarball or dir containing test result dirs.

    Example:
        /var/log/qaset/log/gzip-ACAP2-20151216-20151216T110220.tar.bz2
        /var/log/qa/ctcs2
    '''

    RESULT_FILE_NAME    = 'test_results'
    TARBALL_PATTERN     = '*.tar.*'

    def __init__(self, log_dir, logger=None):
        if logger is None:
            self.logger = logging.getLogger(self.__class__.__name__)
        else:
            self.logger = logger
        self.log_dir = log_dir
        self.results = {}
        self.extraction_dir = None

    def mk_extraction_dir(self):
        tmp_dir = '/tmp'
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        extraction_dir = os.path.join(tmp_dir,
                        "testsuite-log-parser_%s" % (timestamp))
        try:
            os.mkdir(extraction_dir, '0755')
        except OSError, e:
            raise OSError("Dir %s already exists: %s" % (extraction_dir, e))
        except IOError, e:
            raise IOError("Failed to create %s for extraction: %s" % (extraction_dir, e))
        self.extraction_dir = extraction_dir
        return extraction_dir

    def extract(self, tarball):
        cmd = "tar xf '%s' -C '%s'" % (tarball, self.extraction_dir)
        ret = subprocess.call(cmd, shell=True)
        assert ret == 0, "Extraction failed: %s" % (cmd)

    def parse(self):
        test_result_dirs = []
        self.mk_extraction_dir()
        # Handle each entry in log_dir
        for entry in glob.glob(os.path.join(self.log_dir, '*')):
            if fnmatch.fnmatch(os.path.basename(entry), '*.tar.*'):
                try:
                    self.extract(full_path)
                except AssertionError, e:
                    self.logger.warning("Failed to extract %s. Skipping..." % (full_path))
            elif os.isdir(full_path):
                test_result_dirs.append(full_path)
            else:
                self.logger.warning("Unknown entry '%s'. Skipping..." % (entry))
        # Handle extracted entries
        test_result_dirs.extend(glob.glob(os.path.join(self.extraction_dir, '*')))
        # Parse each dir
        for entry in test_result_dirs:
            result_file = os.path.join(path, self.RESULT_FILE_NAME)
            if not os.access(result_file, os.R_OK):
                self.logger.warning("Failed to read test result: %s" % (result_file))
                continue
            # Create ResultFileParser for each file
            p = ResultFileParser(result_file, self.logger)
            p.parse()


if __name__ == '__main__':
    logging.basicConfig()
    logger = logging.getLogger('junit_gen')
