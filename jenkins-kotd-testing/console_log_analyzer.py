#!/usr/bin/env python
import argparse
import urllib
import re
from string import Template


def get_log_url(url):
    url = url.strip()
    if url.endswith('console'):
        url = ''.join([url, 'Full'])
    return url

def get_log(url):
    f = urllib.urlopen(url)
    log = f.read()
    f.close()
    return log

def get_correct_status(status):
    rules = {'LED': 'FAILED',
        'SED': 'PASSED',
        'PED': 'SKIPPED',
        'OUT': 'TIMEOUT',
        'ME': 'TIMEOUT',
        'PP': 'SKIPPED',
        'IP': 'SKIPPED',
        'IL': 'FAILED',
        'SS': 'PASSED',}
    for key, value in rules.items():
        if key in status:
            return value
    raise ValueError('Invalid type: %s' % (status))

def log_handler(log):
    def testsuites_handler(match, value, lines, index):
        res = match.group(1)
        if res == '_reboot_off':
            return value
        value = set(value)
        value.add(res)
        return list(value)

    def submission_handler(match, value, lines, index):
        name = match.group(1)
        for i in range(index + 1, index + 10):
            line = lines[i]
            match = re.search(r'Submission id.*?ID\s*(\d+)\s*:.*?(https?://.*?)\'',
                                line,
                                re.IGNORECASE)
            if match is not None:
                value[name] = {'id': match.group(1), 'url': match.group(2)}
                return value
        value[name] = {}
        return value

    def screenlog_handler(match, value, lines, index):
        name = match.group(1)
        if not value.has_key(name):
            value[name] = []
        index += 1
        line = lines[index]
        while re.search(r'Get submission id.*?submission-([\w_\-]+)\.log',
                        line,
                        re.IGNORECASE) is None:
            if re.search(r'\*+.*?Test in progress.*?\*+',
                        line, re.IGNORECASE) is not None:
                screenlog = []
                seq = 0
                total = 0
                test = None
                bitmap = None
                while re.search(r'\*+.*?Test run complete.*?\*+',
                                line, re.IGNORECASE) is None:
                    match = re.search(r'\[\s*(\d+)/(\d+)\s*\]\s*([\w_\-\.]+)\s+.*?([A-Z]+)\s*\(([^\s]+)\)',
                                        line)
                    if match is not None:
                        seq = int(match.group(1))
                        total = int(match.group(2))
                        if bitmap is None:
                            bitmap = [0 for i in range(total)]
                        bitmap[seq - 1] = 1
                        test = match.group(3)
                        status = get_correct_status(match.group(4))
                        duration = match.group(5)
                        screenlog.append({'test': test, 'seq': seq, 'total': total, 'status': status, 'duration': duration})
                    index += 1
                    line = lines[index]
                # Check if all tests status are available
                if bitmap is not None:
                    missing = []
                    for i in range(len(bitmap)):
                        if bitmap[i] == 0:
                            missing.append(i + 1)
                    if len(missing) != 0:
                        print "Possible missing tests: %s\nSearch for: %d/%d] %s" % (', '.join(map(str, missing)), seq, total, test)
                value[name].append(screenlog)
            index += 1
            line = lines[index]
        return value

    # (name, regexp object, handler)
    rules = [
        ('hostname', r'reserve host\s*([^\s]+)'),
        ('uuid', r'UUID\s*:\s*([^\s]+)'),
        ('testsuites', r'([\w_\-]+)".*?/qaset/list', testsuites_handler),
        ('submissions', r'Get submission id.*?submission-([\w_\-]+)\.log', submission_handler),
        ('screenlog', r'Get file content.*?([\w_\-]+)-\w+\.screenlog', screenlog_handler),
    ]

    results = {
        'hostname': None,
        'uuid': None,
        'testsuites': [],
        'submissions': {},
        'screenlog': {},
    }
    lines = log.splitlines()
    for i in range(len(lines)):
        line = lines[i]
        for rule in rules:
            name = rule[0]
            match = re.search(rule[1], line, re.IGNORECASE)
            if match is not None:
                # Call handler if any
                if len(rule) == 3:
                    results[name] = rule[2](match, results.get(name), lines, i)
                    continue
                # Match string using regex
                if match.lastindex is None:
                    value = match.group(0)
                else:
                    value = match.group(match.lastindex)
                # Store result into dict
                results[name] = value
    return results

def report(log_data):
    s = Template('''=============test report==============
test machine: $hostname
uuid: $uuid

Testsuites:
===========
$testsuites

Failed tests:
=============
$failed_tests

Submission status:
==================
$submission_status

''')
    submission_status = ["Testsuite".ljust(15), "ID".ljust(10), "URL\n"]
    for name in log_data['testsuites']:
        data = log_data['submissions'].get(name, {})
        submission_status.append(name.ljust(15))
        submission_status.append(data.get('id', 'NULL').ljust(10))
        submission_status.append(data.get('url', 'NULL'))
        submission_status.append('\n')

    def filter_test(item):
        if item['status'] == 'FAILED':
            return True
        else:
            return False

    def map_screenlog(screenlog):
        lst = filter(filter_test, screenlog)
        return lst

    def filter_screenlog(screenlog):
        if len(screenlog) == 0:
            return False
        else:
            return True
        
    failed_report = []
    for testsuite, screenlogs in log_data['screenlog'].items():
        screenlogs = map(map_screenlog, screenlogs)
        screenlogs = filter(filter_screenlog, screenlogs)
        if len(screenlogs) != 0:
            failed_report.append('')
            failed_report.append(testsuite)
            failed_report.append('~' * 20)
        for screenlog in screenlogs:
            for item in screenlog:
                line = '%d/%d] %s (%s)' % (item['seq'], item['total'], item['test'], item['duration'])
                failed_report.append(line)
            failed_report.append('-' * 20)
            

    report_data = {
        'hostname': log_data['hostname'],
        'uuid': log_data['uuid'],
        'testsuites': ', '.join(log_data['testsuites']),
        'submission_status': ''.join(submission_status),
        'failed_tests': '\n'.join(failed_report),
    }


    print s.substitute(report_data)

def main():
    parser = argparse.ArgumentParser(description = 'Analyze jenkins kotd console log')
    parser.add_argument('url', metavar='URL', type=str)
    args = parser.parse_args()

    url = get_log_url(args.url)
    log = get_log(url)
    log_data = log_handler(log)

    report(log_data)

#    #for testsuite, screenlogs in data['screenlog'].items():
#        for screenlog in screenlogs:
#            for test, value in screenlog.items():
#                if value['status'] == 'AILED':
#                    print test

if __name__ == '__main__':
    main()
