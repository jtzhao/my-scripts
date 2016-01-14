#!/usr/bin/env python2
import commands
import select
import subprocess
import os
import time

def _monitor_func(screen_monitor):
    epoll = select.epoll()
    epoll.register(screen_monitor.proc.stdout.fileno(), select.EPOLLIN)
    while not screen_monitor.stop:
        events = epoll.poll(10)

class ScreenMonitor(object):
    def __init__(self, pid):
        self.pid = pid
        self.stop = False
        self.monitor_thread = None
        self.monitor()

    def monitor(self):
        self.proc = subprocess.Popen('screen -r %d' % (self.pid),
                                    shell=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)

class Testrun(object):
    # run_script:   Script to trigger test. e.g. /usr/share/qa/qaset/kernel-all-run
    def __init__(self, run_script):
        self.script = run_script
        self.procs = {}             # {pid: proc_obj}

    def __del__(self):
        pass

    def get_pids(self):
        pids = {}
        ret, output = commands.getstatusoutput('screen -list')
        assert ret == 0, "Failed to get screen list"
        lst = re.findall(r'\d+\.[^\s]+', output)
        for item in lst:
            pid, name = item.split('.')
            pids[name] = int(pid)
        return pids

    def get_testsuite_pid(self):
        pids = self.get_pids()
        script_name = os.path.basename(self.script)
        script_name = re.sub(r'-run$', '', script_name)
        for name, pid in pids.items():
            if not name.endswith(script_name):
                return pid
        raise ValueError("No testsuite pid found: %s" % (pids))

    def reset(self):
        ret = commands.getstatus('/usr/share/qa/qaset/qaset reset')
        assert ret == 0, 'Failed to reset testrun'

    def trigger(self):
        ret = commands.getstatus(self.script)
        assert ret == 0, "Failed to run script: %s" % (self.script)

    # Use screen -r to minitor process output
    def monitor(self, pid):
        cmd = 'screen -r %d' % (pid)

    def main_loop(self):

    def run(self):
        self.reset()
        self.trigger()
        # Wait for test to begin
        time.sleep(3)
        pids = self.get_pids()
        for i in range(10):
            time.sleep(3)
            pids = self.get_pids()
            if len(pids) != 0:
                break
        assert len(pids) != 0, "Failed to trigger test"
        for pid in pids.values():
            self.monitor
