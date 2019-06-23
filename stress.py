#!/usr/bin/env python3

import subprocess
import socket
from random import randint

iperf_server = "192.168.55.2"
iperf_min_max_MB = (10, 75)
dd_min_max_MB = (1, 10)
dd_min_max_MB = (50, 100)  # looks more 'stressy' than previous line


def main():
    hostname = socket.gethostname()
    if hostname == "vm2":
        # iperf, stress-ng
        # find out the number of cpus
        with open("/proc/cpuinfo") as f:
            out = f.read()
        ncpu = out.count("processor")
        subprocess.Popen("iperf -u -s >/dev/null", shell=True)
        subprocess.Popen(f"stress-ng --cpu {ncpu} --vm 1 2>/dev/null",
                         shell=True)
        print(f"Stress started: iperf as server (udp),"
              f" stress-ng --cpu {ncpu} --vm 1")
        a = input()
    elif hostname == "vm3":
        # iperf, dd
        bandwidth = randint(iperf_min_max_MB[0] * 8,
                            iperf_min_max_MB[1] * 8)  # MB => Mb
        subprocess.Popen(f"while : ; do "
                         f"iperf -u -b {bandwidth}M -c {iperf_server} "
                         f">/dev/null; done", shell=True)
        throttle = randint(dd_min_max_MB[0], dd_min_max_MB[1])
        subprocess.Popen(f"while : ; do "
                         f"dd if=/dev/zero bs=50M count=10 2>/dev/null | "
                         f"throttle -M {throttle} | "
                         f"dd of=/home/vagrant/dd_out 2>/dev/null; done",
                         shell=True)
        print(f"Stress started: iperf at {round(bandwidth/8)} MB/s (udp), "
              f"dd at {throttle} MB/s")
        a = input()


if __name__ == "__main__":
    main()
