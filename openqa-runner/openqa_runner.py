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


class ProcMonitorThread(threading.Thread):
    def __init__(self, runner):
        self.runner = runner
        super(ProcMonitorThread, self).__init__(name='proc-monitor')

    def remove_exited(self):
        def _filter_proc(proc):
            if proc.poll() is None:
                return True
            return False
        filter(_filter_proc, self.runner.procs)

    def proc_list(self):
        output = subprocess.check_output('screen -list',
                                        shell=True)
        lst = re.findall(r'(\d+)\.([^\s]+)\s*\((\w+)\)', output)
        print lst
        return lst

    # Check status of all procs and use screen -list to find new ones
    def add_new(self):
        lst = self.proc_list()
        for pid, name, status in lst:
            pid = int(pid)
            if status == 'Attached':
                continue
            if self.runner.get_proc_by_pid(pid) is not None:
                continue
            if 'hamsta' in name:
                continue
            proc = ScreenProc(name, pid)
            # Set non-block flag
            fl = fcntl.fcntl(proc.stdout.fileno())
            fcntl.fcntl(proc.stdout.fileno(), fcntl.F_SETFL, fl | os.O_NONBLOCK)
            self.runner.register_proc(proc)

    def run(self):
        while self.runner.stop_monitor_flag == False:
            self.remove_exited()
            self.add_new()
            # TODO
            #time.sleep(30)


class OpenqaRunner(object):
    # run_script:   Script to trigger test. e.g. /usr/share/qa/qaset/run/kernel-all-run
    def __init__(self, run_script):
        self.script = run_script
        self.name = re.sub(r'-run$', '', os.path.basename(self.script))
        self.epoll = select.epoll()
        self.procs = []

    def __del__(self):
        pass

    def get_proc_by_pid(self, pid):
        for proc in self.procs:
            if proc.pid == pid:
                return proc
        return None

    def get_proc_by_fd(self, fd):
        for proc in self.procs:
            if proc.stdout.fd() == fd:
                return proc
        return None

    def trigger(self):
        subprocess.check_call(self.script,
                                shell=True)
        time.sleep(10)

    def register_proc(self, proc):
        self.epoll.register(proc.stdout.fd(), select.EPOLLIN)
        self.procs[proc.stdout.fd()] = {'popen': proc, 'buf': []}

    def main_loop(self):
        while len(self.procs) != 0:
            events = self.epoll.poll(30)
            for fd, event in events:
                proc = self.get_proc_by_fd(fd)
                try:
                    line = proc.stdout.readline()
                    while len(line) != 0:
                        proc.buf.append(line)
                        line = proc.stdout.readline()
                except IOError, e:
                    break
            # TODO: refresh ui
            for proc in self.procs:
                print '=' * 40 + proc.name + '=' * 40
                print '\n'.join(proc.buf)

    def start_monitor(self):
        self.stop_monitor_flag = False
        self.monitor_thread = ProcMonitorThread(self)
        self.monitor_thread.start()
        time.sleep(1)
        
    def stop_monitor(self):
        self.stop_monitor_flag = True
        self.monitor_thread.join(35)

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
