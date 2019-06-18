# Stress monitor hands-on work

- Trained technologies: Vagrant, Ansible, Zabbix, Python, PTP4L, VirtualBox, Ubuntu.
- Stress software: stress-ng, iperf, dd + throttle.
- Monitoring software: zabbix.
- Monitored indicators: CPU load, Memory, IO, network, PTP daemon state and PTP master offset.
- Additional rules: monitoring indicators should be reported every 100 ms or less.

# Deploy instructions:
- install Vagrant and VirtualBox
- clone repository
- run 'vagrant up' in repository directory
- wait for deploy
- open http://127.0.0.1/zabbix to watch perfomance graphs, default credentials admin:zabbix
