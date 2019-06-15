#!/usr/bin/env bash

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y zabbix-server-mysql zabbix-frontend-php php-mysql ansible
a2enconf zabbix-frontend-php

sudo mysql -e "create database zabbix character set utf8"
sudo mysql -e "grant all on zabbix.* to 'zabbix'@'localhost' identified by 'zabbix'"
cat /vagrant/zabbix.sql | mysql -u zabbix -pzabbix zabbix
echo DBHost=localhost >> /etc/zabbix/zabbix_server.conf
echo DBPassword=zabbix >> /etc/zabbix/zabbix_server.conf

sed -i 's/# php_value date.timezone Europe\/Riga/php_value date.timezone Europe\/Moscow/' /etc/apache2/conf-available/zabbix-frontend-php.conf
cp /vagrant/zabbix.conf.php /etc/zabbix/
chmod 644 /etc/zabbix/zabbix.conf.php

systemctl reload apache2
systemctl start zabbix-server
systemctl enable zabbix-server

# this ^^ could be included in ansible too
ANSIBLE_HOST_KEY_CHECKING=False ansible-playbook -i /vagrant/ansible_hosts /vagrant/ansible_playbook
