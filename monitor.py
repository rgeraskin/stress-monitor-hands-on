#!/usr/bin/env python3

import datetime
import time
import subprocess
import netifaces
import numpy
import socket
from threading import Thread
from queue import Queue
from pprint import pprint

zabbix_server = "192.168.55.4"

start_delay = 0.1
estimated_delay_max = 0.1
estimated_delay_min = 0.06
delay_raise_by = 0.01
delay_decrease_by = 0.01

#start_delay = 3
#estimated_delay_max = 4
#estimated_delay_min = 2
#delay_raise_by = 0.1
#delay_decrease_by = 0.2

samples = 100
samples_inc = 0

results = Queue()
delays = {"Get": [], "Send": []}

def adjust_delay(who, delay, t1, t2):
    real_delay = t2 - t1
    #print(f"{who} set delay:", round(delay, 3))
    #print(f"{who} real delay:", round(real_delay, 3))
    #print()

    if real_delay > estimated_delay_max and delay - delay_decrease_by > 0:
        delay -= delay_decrease_by
    elif real_delay < estimated_delay_min:
        delay += delay_raise_by
        
    delays[who].append(real_delay)
    return delay

def get_measures(result):
    # I read /proc directly because atop is too slow IMO

    delay = start_delay
    i = 0
    while i < samples:
        i += samples_inc
        t1 = time.time()
        
        # CPU
        with open("/proc/loadavg") as f:
            out = f.read()
        out = out.split()
        result["cpl"]["avg1"] = float(out[0])
        result["cpl"]["avg5"] = float(out[1])
        result["cpl"]["avg15"] = float(out[2])

        # Memory
        with open("/proc/meminfo") as f:
            out = f.readlines()
        for l in out:
            l = l.split()
            if l:
                if l[0] == "MemTotal:":
                    memtotal = int(l[1])
                elif l[0] == "MemFree:":
                    memfree = int(l[1])
        result["mem"]["free_perc"] = round(memfree / memtotal * 100, 2)

        # IO
        # Because of the low measures interval there will be peaks and falls.
        # So you should look at average value or implement a measures interval increasing hack.
        with open("/proc/diskstats") as f:
            val = f.readlines()
        for l in val:
            l = l.strip().split()
            if l:
                name = l[2]
                if result["dsk"]["_disk_to_mon"] != name:
                    continue
                val = int(l[12]) # time spent doing I/Os (ms)
                if name not in result["dsk"]:
                    result["dsk"][name] = {}
                if "_val" in result["dsk"][name]:
                    io_time_spent_delta = val - result["dsk"][name]["_val"]             # ms
                    measures_time_spent_delta = (t1 - result["dsk"]["_time"])           # seconds
                    utilization = io_time_spent_delta / measures_time_spent_delta / 10  # percent
                    result["dsk"][name]["busy_perc"] = round(utilization, 2)
                result["dsk"][name]["_val"] = val
        result["dsk"]["_time"] = t1

        # Network
        # Because of the low measures interval there may be peaks and falls.
        # So you should look at average value or implement a measures interval increasing hack.
        with open("/proc/net/dev") as f:
            out = f.readlines()
        for l in out:
            l = l.split()
            name = l[0][:-1]
            if name in result["net"]:
                if "_rx" in result["net"][name]:
                    rx_delta = int(l[1]) - result["net"][name]["_rx"]
                    tx_delta = int(l[9]) - result["net"][name]["_tx"]
                    time_delta = t1 - result["net"]["_time"]

                    if result["net"][name]["_full_duplex"]:
                        result["net"][name]["_activity_perc"] = (rx_delta + tx_delta) 
                    else:
                        result["net"][name]["_activity_perc"] = max(rx_delta, tx_delta)
                    result["net"][name]["_activity_perc"] = result["net"][name]["_activity_perc"] * 8 / 1024 / 1024 / time_delta
                    result["net"][name]["_activity_perc"] = round(result["net"][name]["_activity_perc"] / result["net"][name]["_speed_mbps"] * 100, 2)
                result["net"][name]["_rx"] = int(l[1])
                result["net"][name]["_tx"] = int(l[9])
                if "_activity_perc_log" in result["net"][name]:
                    result["net"][name]["_activity_perc_log"].append(result["net"][name]["_activity_perc"])
                    result["net"][name]["avg_perc"] = round(sum(result["net"][name]["_activity_perc_log"])/len(result["net"][name]["_activity_perc_log"]), 2)
                    result["net"][name]["min_perc"] = round(min(result["net"][name]["_activity_perc_log"]), 2)
                    result["net"][name]["max_perc"] = round(max(result["net"][name]["_activity_perc_log"]), 2)
                    result["net"][name]["perc95"] = round(numpy.percentile(result["net"][name]["_activity_perc_log"], 95), 2)
                    result["net"][name]["perc99"] = round(numpy.percentile(result["net"][name]["_activity_perc_log"], 99), 2)
                    # BTW do not need all of this because of zabbix has it's own functional for this ^^ (min, max, avg, may be percentile too)
                else:
                    result["net"][name]["_activity_perc_log"] = []        
        result["net"]["_time"] = t1
        
        # PTP
        out = subprocess.run("sudo journalctl -b --no-pager -u ptp4l -n 50", shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()
        out = out.split("\n")[1:]
        result["ptp"]["status"] = out[-1].strip()
        for l in out[::-1]:
            if "master offset" in l:
                result["ptp"]["master_offset"] = l.split("master offset")[1].split()[0]
                break
            elif "grand master" in l:
                result["ptp"]["master_offset"] = 0
                break

        # Intervals
        time.sleep(delay)
        t2 = time.time()
        result["interval"]["get"] = t2 - t1

        results.put(result)
        delay = adjust_delay("Get", delay, t1, t2)

def flatten(dictionary, prefix=[], result={}):
    for k, v in dictionary.items():
        if k[0] == '_':
            continue
        elif isinstance(v, dict):
            flatten(v, prefix+[k], result)
        else:
            prefix_str = '_'.join(prefix + [k])
            if not prefix_str in result:
                result[prefix_str] = {}
            result[prefix_str] = v
    return result

def send_measures():
    hostname = socket.gethostname()
    
    delay = start_delay
    i = 0
    while i < samples:
        i += samples_inc
        t1 = time.time()
           
        result = results.get()
        fresult = flatten(result)
        for k, v in fresult.items():
            if k[:3] == "net" or k[:3] == "dsk":
                k = k.split("_")
                del(k[1])
                k = "_".join(k)
            #print(k, v)
            #subprocess.Popen(f"/usr/bin/zabbix_sender -z {zabbix_server} -s {hostname} -k {k} -o".split() + [str(v)], stdout=subprocess.DEVNULL)
            subprocess.Popen(f"/usr/bin/zabbix_sender -z {zabbix_server} -s {hostname} -k {k} -o '{v}' >/dev/null", shell=True)
        #print()
        #pprint(result)
        
        # Intervals
        time.sleep(delay)
        t2 = time.time()
        subprocess.Popen(f"/usr/bin/zabbix_sender -z {zabbix_server} -s {hostname} -k interval_send -o {t2 - t1} >/dev/null", shell=True)

        delay = adjust_delay("Send", delay, t1, t2)

def main():
    result = {}
    result["cpl"] = {}
    result["mem"] = {}
    result["dsk"] = {}
    result["net"] = {}
    result["ptp"] = {}
    result["interval"] = {}
    
    # find out the number of cpus
    with open("/proc/cpuinfo") as f:
        out = f.read()
    result["cpl"]["_numcpu"] = out.count("processor")

    # find out what ifaces are full duplex, ifaces speed
    out = subprocess.run("dmesg", shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode()
    for l in out.split("\n"):
        if "Duplex," in l:
            name = l.split("]")[1].strip().split()[1]
            result["net"][name] = {}
            result["net"][name]["_full_duplex"] = "Full Duplex" in l
            result["net"][name]["_speed_mbps"] = int(l.split("Mbps")[0].strip().split()[-1]) # are there any nics with speed counted less than Mbps?
    
	# find out what iface is responsible for disered net
    net_to_mon = ".".join(zabbix_server.split(".")[:3]+["255"])
    for iface in result["net"]:
        if net_to_mon in [x['broadcast'] for x in netifaces.ifaddresses(iface)[netifaces.AF_INET]]:
            break
    result["net"], result["net"][iface] = {}, result["net"][iface] # python rulez
    
    # find out rootfs device
    with open("/proc/mounts") as f:
        conts = f.readlines()
    for l in conts:
        l = l.split(" ")
        if l[1] == '/':
            disk_to_mon = l[0].split("/")[-1]
            result["dsk"]["_disk_to_mon"] = disk_to_mon
            break

    get_thread = Thread(target=get_measures, args=(result,))
    send_thread = Thread(target=send_measures)

    get_thread.start()
    send_thread.start()
    get_thread.join()
    send_thread.join()
    
    print("Get average time spent: ", sum(delays["Get"]) / len(delays["Get"]))
    print("Send average time spent:", sum(delays["Send"]) / len(delays["Send"]))

if __name__ == "__main__":
    main()