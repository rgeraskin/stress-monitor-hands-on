# Stress monitor hands-on work

- Trained technologies: Vagrant, Ubuntu, Zabbix, Ansible, Python, PTP4L.
- Stress software: stress-ng, iperf, dd + throttle.
- Monitoring software: zabbix.
- Monitored indicators: CPU load, Memory, IO, network, PTP daemon state and PTP master offset.
- Additional rules: monitoring indicators should be reported every 100 ms or less.

# Deploy instructions:
- install Vagrant
- clone repository
- run 'vagrant up' in repository directory
- wait for deploy
- open http://127.0.0.1/zabbix to watch perfomance graphs
