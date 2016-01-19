#!/usr/bin/env python
import datetime
import fcntl
import os
import select
import subprocess
import threading
import random
import re
import time
import logging


class MyPopen(subprocess.Popen):
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

    def __del__(self):
        pass

    def heartbeat(self):
        heart_rate = random.random() * 40 + 60
        msg = "HR: %.7fbpm" % (heart_rate)
        return msg

    def trigger(self):
        subprocess.check_call(self.script,
                                shell=True)
        time.sleep(5)

    def list_proc(self):
        def _filter_proc_list(item):
            pid, name, status = item
            if 'hamsta' in name or status != 'Detached':
                return False
            return True

        def _pid_to_int(item):
            pid, name, status = item
            pid = int(pid)
            return pid, name

        proc = MyPopen('list-proc', 'screen -list')
        ret = proc.wait()
        output = proc.stdout.read()
        lst = re.findall(r'(\d+)\.([^\s]+)\s*\((\w+)\)', output)
        lst = filter(_filter_proc_list, lst)
        lst = map(_pid_to_int, lst)
        return lst

    def testrun_finished(self, lst):
        for pid, name in lst:
            if name.endswith("-%s" % (self.name)):
                return False
        return True

    def get_test_proc(self, lst):
        for pid, name in lst:
            if name.endswith("-%s" % (self.name)):
                continue
            return pid, name
        return None, None

    def monitor_test_proc(self, pid, name):
        self.proc = MyPopen(name, 'screen -r %d' % (pid))
        self.timestamp = datetime.datetime.now()

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
                if self.proc.poll() is None:
                    logging.info('"%s" running for %ds(%s)' % (self.proc.name, td.seconds, self.heartbeat()))
                else:
                    logging.info('"%s" finished in %.1fm(%s)' % (self.proc.name, td.seconds/60.0, self.heartbeat()))
                    self.proc = None
                    self.timestamp = None
            if self.proc is None:
                pid, name = self.get_test_proc(lst)
                if pid is None:
                    logging.info('No test process found(%s)' % (self.heartbeat()))
                    time.sleep(10)
                else:
                    logging.info('Test process found: %d.%s(%s)' % (pid, name, self.heartbeat()))
                    self.monitor_test_proc(pid, name)
            lst = self.list_proc()
        logging.info('Testrun finished(%s)' % (self.heartbeat()))

    def reset(self):
        subprocess.check_call('/usr/share/qa/qaset/qaset reset',
                                shell=True)

    def run(self):
        self.reset()
        self.trigger()
        self.main_loop()


if __name__ == '__main__':
    random.seed()
    logging.basicConfig(format='\r[%(asctime)s] %(levelname)s: %(message)s',
                        datefmt='%H:%M:%S',
                        level=logging.INFO)
    runner = OpenqaRunner('/usr/share/qa/qaset/run/kernel-all-run')
    runner.run()
