#!/usr/bin/env python
import fcntl
import os
import select
import subprocess
import threading
import re
import time


class ScreenProc(subprocess.Popen):
    def __init__(self, name, pid):
        self.name   = name
        self.buf    = []
        cmd = 'screen -r %d' % (pid)
        super(ScreenProc, self).__init__(cmd, shell=True, stdin=None,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT)


class OpenqaRunner(object):
    # run_script:   Script to trigger test. e.g. /usr/share/qa/qaset/run/kernel-all-run
    def __init__(self, run_script):
        self.script = run_script
        self.name = re.sub(r'-run$', '', os.path.basename(self.script))
        self.epoll = select.epoll()
        self.proc = None
        self.ret = None

    def __del__(self):
        pass

    def proc_list(self):
        output = subprocess.check_output('screen -list',
                                        shell=True)
        lst = re.findall(r'(\d+)\.([^\s]+)\s*\((\w+)\)', output)
        return lst

    def trigger(self):
        subprocess.check_call(self.script,
                                shell=True)
        time.sleep(5)

    def get_proc_ret(self):
        self.ret = self.proc.poll()

    def proc_fetch(self):
        lst = self.proc_list()
        for pid, name, status in lst:
            pid = int(pid)
            if status == 'Attached' or self.name in name
                                    or 'hamsta' in name:
                continue
            self.proc = ScreenProc(name, pid)
            break
        assert self.proc is not None, "Failed to get test process"
        # Set non-block flag
        fl = fcntl.fcntl(self.proc.stdout.fileno())
        fcntl.fcntl(self.proc.stdout.fileno(), fcntl.F_SETFL, fl | os.O_NONBLOCK)
        # Register fd for epoll
        self.epoll.register(self.proc.stdout.fileno(), select.EPOLLIN)

    def proc_remove(self):
        if self.proc is None:
            return
        # Unregister fd for epoll
        self.epoll.unregister(self.proc.stdout.fileno())
        # Try to get return code
        ret = self.proc.poll()
        if ret is None:
            self.proc.kill()

    def proc_readlines(self):
        try:
            line = self.proc.stdout.readline()
            while len(line) != 0:
                self.proc.buf.append(line)
                line = self.proc.stdout.readline()
        except IOError, e:
            pass

    def proc_exited(self):
        self.proc_get_ret

    def main_loop(self):
        while len(self.proc_list()) != 0:
            try:
                self.proc_fetch()
            except AssertionError, e:
                time.sleep(5)
                continue
            events = self.epoll.poll(30)
            for fd, event in events:
                assert fd == self.proc.stdout.fileno(), "Fatal error: fd mismatch"
                self.proc_readlines()
            # If proc exited, remove it
            if self.proc.poll() is not None:

            # TODO: refresh ui
            for proc in self.procs:
                print '=' * 40 + proc.name + '=' * 40
                print '\n'.join(proc.buf)

    def reset(self):
        subprocess.check_call('/usr/share/qa/qaset/qaset reset',
                                shell=True)

    def run(self):
        self.reset()
        self.trigger()
        self.start_monitor()
        self.main_loop()
        self.stop_monitor()

runner = OpenqaRunner('/usr/share/qa/qaset/run/kernel-all-run')
runner.run()
