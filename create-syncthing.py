#!/usr/bin/python
import os
import sys
import docker as Docker
from pwd import getpwnam
from syslog import syslog

if len(sys.argv) < 2:
    print >> sys.stderr, "Usage:", sys.argv[0], "<user>"
    sys.exit(-1)

user = sys.argv[1]
docker = Docker.Client(base_url='unix://var/run/docker.sock')

uid = getpwnam(user).pw_uid

try:
    container = docker.inspect_container("syncthing-" + user)
    print >> sys.stderr, "Syncthing container for", user, "already exists."
    sys.exit(10)
except Docker.errors.NotFound, e:
    pass

container_ip = None
try:
    network = docker.inspect_network("syncthing")

    for octet in range(10, 250):
        exists = False
        for c in network['Containers']:
            if c['IPv4Address'] == "172.18.1." + str(octet) + "/24":
                exists = True
                break
        if not exists:
            container_ip = "172.18.1." + str(octet)
            break

    if container_ip is None:
        print sys.stderr, "No IP Addresses remaining in network for new container."
        sys.exit(2)
except Docker.errors.NotFound, e:
    syslog("Creating syncthing network...")
    ipam = Docker.utils.create_ipam_config(
        pool_configs=[Docker.utils.create_ipam_pool(subnet='172.18.1.0/24')]
    )
    docker.create_network("syncthing", driver="bridge", ipam=ipam)
    container_ip = '172.18.1.10'

syslog("Creating Syncthing container for " + user + " with IP address " + container_ip)
container = docker.create_container(
    image="tianon/syncthing",
    name="syncthing-" + user,
    entrypoint="/usr/local/bin/syncthing --no-restart --no-browser --gui-address=http://0.0.0.0:8384 -home=/home/" + user + "/.config/syncthing",
    user=uid,
    volumes=["/home/" + user, "/etc/localtime"],
    host_config=docker.create_host_config(restart_policy={
        'MaximumRetryCount': 0, 'Name': 'always'
    }, binds=[
        '/home/' + user + ':/home/' + user + ':rw',
        '/etc/localtime:/etc/localtime:ro'
    ]),
    networking_config=docker.create_networking_config({
        'syncthing': docker.create_endpoint_config(
            ipv4_address=container_ip,
            aliases=["syncthing-" + user]
        )
    })
)

syslog('Starting container...')
docker.start(container=container.get('Id'))

syslog("Configuring httpd...")
config = open('/etc/httpd/conf.d/includes/syncthing/' + user + '.conf', 'w')
print >> config, "ProxyPass /syncthing/" + user + " http://" + container_ip + ":8384"
print >> config, "ProxyPassReverse /syncthing/" + user + " http://" + container_ip + ":8384"
config.close()

syslog('Reloading httpd...')
if os.system('apachectl configtest') == 0:
    os.system('systemctl restart httpd')
    