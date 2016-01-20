#!/usr/bin/env python
import argparse
import datetime
import fcntl
import glob
import os
import select
from string import Template
import subprocess
import threading
import random
import re
import time
import logging

# Hack logging module to add heartbeat info
_orig_log = logging.Logger._log

def _new_log(self, level, msg, args, exc_info=None, extra=None):
    heart_rate = random.random() * 40 + 60
    msg = "%s (%.7fbpm)" % (msg, heart_rate)
    return _orig_log(self, level, msg, args, exc_info, extra)

logging.Logger._log = _new_log

def run_with_heartbeat(cmd, msg, begin_msg=None, succ_msg=None,
                        fail_msg=None, no_check=False, interval=60):
    if begin_msg is not None:
        logging.info(begin_msg)
    logging.info("># %s" % (cmd))
    proc = PopenWithName('', cmd)
    count = 0
    while proc.poll() is None:
        count += 1
        if count >= interval:
            logging.info(msg)
            count = 0
        time.sleep(1)
    if no_check or proc.poll() == 0:
        if succ_msg is not None:
            logging.info(succ_msg)
    else:
        if fail_msg is not None:
            tmpl = Template(fail_msg)
            fail_msg = Template(fail_msg).safe_substitute(exitstatus=str(proc.poll()))
            logging.info(fail_msg)
    return proc.poll(), proc.stdout.read()

def zypper_list_repo():
    def _strip(s):
        return s.strip()

    repos = []
    cmd = "zypper repos -u"
    output = subprocess.check_output(cmd, shell=True)
    for line in output.splitlines():
        if re.search(r'^\d+\s*\|', line):
            arr = line.split('|')
            arr = map(_strip, arr)
            repo = {}
            keys = ['id', 'alias', 'name', 'enabled', 'gpg', 'refresh', 'uri']
            for i in range(len(arr)):
                repo[keys[i]] = arr[i]
            repos.append(repo)
    return repos

def zypper_add_repo(name, url):
    logging.info('Adding repo "%s"' % (name))
    cmd = "zypper -n addrepo -f '%s' '%s'" % (url, name)
    subprocess.check_call(cmd, shell=True)

def zypper_remove_repo(name):
    logging.info('Removing repo "%s"' % (name))
    cmd = "zypper -n removerepo %s" % (name)
    subprocess.check_call(cmd, shell=True)

def zypper_remove_all_repos():
    lst = zypper_list_repo()
    for repo in lst:
        zypper_remove_repo(repo['name'])

def zypper_refresh():
    logging.info('Refreshing all repos')
    cmd = "zypper -n --gpg-auto-import-keys refresh"
    subprocess.check_call(cmd, shell=True)

def zypper_install(package):
    logging.info('Installing package "%s"' % (package))
    cmd = "zypper -n install -y %s" % (package)
    subprocess.check_call(cmd, shell=True)

def create_qaset_config(testsuites):
    # Create dirs
    os.makedirs('/root/qaset')
    # Write to config file
    s = Template("echo 'SQ_TEST_RUN_LIST=(\n$testsuites\n)")
    s.substitute(testsuites=testsuites)
    with file('/root/qaset/config', 'w') as f:
        f.write(s)

def init(args):
    random.seed()
    assert args.test is not None, "No testsuites provided. Please use the -t option"
    args.test = args.test.split(',')
    if args.package is None:
        args.package = ['qa_testset_automation',]
    # Remove existing repos
    zypper_remove_all_repos()
    # Add repos
    zypper_add_repo('main', args.main_repo)
    zypper_add_repo('sdk', args.sdk_repo)
    zypper_add_repo('qa', args.qa_repo)
    zypper_refresh()
    # Install packages
    zypper_install(' '.join(args.package))
    # Create config file
    create_qaset_config()

def upload_log(log_tarball, upload_url_prefix):
    upload_url = "%s/uploadlog/%s"  % (log_tarball, upload_url_prefix,
                                        os.path.basename(log_tarball))
    cmd = "curl --form upload='%s' '%s'" % (log_tarball, upload_url)
    return run_with_heartbeat(cmd,
                        'Uploading "%s"' % (log_tarball),
                        succ_msg='Upload succeeded',
                        fail_msg='Upload failed with exit code $exitstatus')

def upload_all_logs(log_dir, upload_url_prefix, pattern='*.tar.*'):
    for item in glob.glob(os.path.join(log_dir, pattern)):
        upload_log(item, upload_url_prefix)



class PopenWithName(subprocess.Popen):
    def __init__(self, name, cmd):
        self.name = name
        super(self.__class__, self).__init__(cmd, shell=True, stdin=None,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT)

class OpenqaRunner(object):
    # run_script:   Script to trigger test. e.g. /usr/share/qa/qaset/run/kernel-all-run
    def __init__(self, run_script):
        self.script = run_script
        self.name = re.sub(r'-run$', '', os.path.basename(self.script))
        self.proc = None                # Subprocess of 'screen -r <pid>'
        self.main_proc = None

    def __del__(self):
        pass

    def start_test(self):
        logging.info("Starting %s testing" % (self.name))
        subprocess.check_call(self.script, shell=True, stdin=None,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        for i in range(20):
            lst = self.list_proc()
            if len(lst) == 0:
                time.sleep(0.5)
            else:
                return
        raise RuntimeError("Failed to start test: %s" % (self.script))

    def list_proc(self):
        def _filter_proc_list(item):
            blacklist = ['hamsta', ]
            pid, name, status = item
            for item in blacklist:
                if item in name:
                    return False
            return True

        def _pid_to_int(item):
            pid, name, status = item
            pid = int(pid)
            return pid, name, status

        proc = PopenWithName('list-proc', 'screen -list')
        ret = proc.wait()
        output = proc.stdout.read()
        lst = re.findall(r'(\d+)\.([^\s]+)\s*\((\w+)\)', output)
        lst = filter(_filter_proc_list, lst)
        lst = map(_pid_to_int, lst)
        return lst

    def testrun_finished(self, lst=None):
        if lst is None:
            lst = self.list_proc()
        for pid, name, status in lst:
            if name.endswith("-%s" % (self.name)):
                return False
        return True

    def start_main_monitor(self, lst=None):
        if lst is None:
            lst = self.list_proc()
        for pid, name, status in lst:
            if name.endswith("-%s" % (self.name)):
                logging.info("Main process found: %d.%s" % (pid, name))
                self.main_proc = PopenWithName(name, 'screen -r %d' % (pid))
                return
        raise RuntimeError("No main process found")

    def stop_main_monitor(self):
        if self.main_proc is not None:
            # Fetch exitstatus to prevent zombie processes
            ret = self.main_proc.poll()
            if ret is None:
                logging.info("Killing main process...")
                self.main_proc.kill()
            else:
                logging.info("Main process exited")

    def start_test_monitor(self, lst=None):
        if lst is None:
            lst = self.list_proc()
        for pid, name, status in lst:
            if name.endswith("-%s" % (self.name)):
                continue
            logging.info('Test process found: %d.%s' % (pid, name))
            self.proc = PopenWithName(name, 'screen -r %d' % (pid))
            self.timestamp = datetime.datetime.now()
            return
        raise RuntimeError("No test process found")

    def test_proc_finished(self):
        if self.proc.poll() is None:
            return False
        return True

    def main_loop(self, interval=3):
        lst = self.list_proc()
        while self.testrun_finished(lst) == False:
            if self.proc is not None:
                time.sleep(interval)
                td = datetime.datetime.now() - self.timestamp
                if self.test_proc_finished():
                    logging.info('"%s" finished in %.1fm' % (self.proc.name, td.seconds/60.0))
                    self.proc = None
                    self.timestamp = None
                else:
                    logging.info('"%s" running for %ds' % (self.proc.name, td.seconds))
            if self.proc is None:
                try:
                    self.start_test_monitor(lst)
                except RuntimeError, e:
                    logging.info('No test process found')
                    time.sleep(10)
            lst = self.list_proc()

    def reset(self):
        logging.info("Resetting testset")
        subprocess.check_call('/usr/share/qa/qaset/qaset reset',
                                shell=True, stdin=None,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)

    def run(self):
        self.reset()
        self.start_test()
        self.start_main_monitor()
        self.main_loop()
        self.stop_main_monitor()

if __name__ == '__main__':
    # Parse args
    parser = argparse.ArgumentParser(description='OpenQA test runner')
    parser.add_argument('script', type=str,
                        help='Script to start testing')
    parser.add_argument('-u', '--upload-url-prefix', metavar='URL', dest='upload_url',
                        type=str, required=True, help='Upload url prefix')
    parser.add_argument('-t', '--testsuite', metavar='TESTSUITE', dest='test',
                        type=str, required=True, help='Testsuites to run. Example: lvm2,gzip,ltp')
    parser.add_argument('-l', '--log-dir', metavar='DIR', dest='log_dir',
                        type=str, required=True, default='/var/log/qaset/log',
                        help='Log dir. Default: /var/log/qaset/log')
    parser.add_argument('-s', '--submission-dir', metavar='DIR', dest='submission_dir',
                        type=str, required=True, default='/var/log/qaset/submission',
                        help='Submission dir. Default: /var/log/qaset/submission')
    parser.add_argument('--main-repo', metavar='URL', dest='main_repo',
                        type=str, required=True,
                        help='Main repo url')
    parser.add_argument('--sdk-repo', metavar='URL', dest='sdk_repo',
                        type=str, required=True,
                        help='SDK repo url')
    parser.add_argument('--qa-repo', metavar='URL', dest='qa_repo',
                        type=str, required=True,
                        help='QA repo url')
    parser.add_argument('-p', '--package', action='append', dest='package',
                        help='Packages to install with zypper')
    args = parser.parse_args()
    print args
    # Init
    init(args)
    logging.basicConfig(format='\r<%(asctime)s> [%(levelname)s] %(message)s\r',
                        datefmt='%H:%M:%S',
                        level=logging.INFO)
    # Running test
    runner = OpenqaRunner(args.script)
    runner.run()
    # Upload logs
    upload_all_logs(args.log_dir, args.upload_url)
