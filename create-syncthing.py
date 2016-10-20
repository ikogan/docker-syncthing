#!/usr/bin/python
import os
import sys
import argparse
import docker as Docker
from pwd import getpwnam
from syslog import syslog

parser = argparse.ArgumentParser(description='Create a Syncthing Docker ' +
                                 'container for a given user.')
parser.add_argument('--disable-upnp', dest='disable_upnp', action='store_true',
                    help='Disable UPnP Port Mapping')
parser.add_argument('--relay', dest='relay', action='store',
                    help='Relay server address.')
parser.add_argument('--relay-container', dest='relay_container',
                    action='store', help='Container hosting the relay ' +
                    'in case linkage between containers is necessary.')
parser.add_argument('--disable-relaying', dest='disable_relay',
                    action='store_true',
                    help='Disable relaying entirely.')
parser.add_argument('--discovery', dest='discovery', action='store',
                    help='Discovery server address.')
parser.add_argument('--discovery-container', dest='discovery_container',
                    action='store', help='Container hosting the discovery ' +
                    'server in case linkage between containers is necessary.')
parser.add_argument('--skip-httpd', dest='skip_httpd', action='store_true',
                    help='Skip creating an httpd configuration.')
parser.add_argument('--expose', dest='ports', action='store',
                    help='Expose a range of ports for the ST protocol.')
parser.add_argument('user', nargs=1)

args = parser.parse_args()

user = args.user[0]
docker = Docker.Client(base_url='unix://var/run/docker.sock')

uid = getpwnam(user).pw_uid
gid = getpwnam(user).pw_gid

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
        print sys.stderr, \
            "No IP Addresses remaining in network for new container."
        sys.exit(2)
except Docker.errors.NotFound, e:
    syslog("Creating syncthing network...")
    ipam = Docker.utils.create_ipam_config(
        pool_configs=[Docker.utils.create_ipam_pool(subnet='172.18.1.0/24')]
    )
    network = docker.create_network("syncthing", driver="bridge", ipam=ipam)
    container_ip = '172.18.1.10'

environment = {}

if args.disable_upnp:
    environment['DISABLE_UPNP'] = "True"
if args.discovery is not None:
    environment['DISCOVERY_SERVER'] = args.discovery
if args.relay is not None:
    environment['RELAY_SERVER'] = args.relay
if args.disable_relay:
    environment['DISABLE_RELAY'] = "True"

syslog("Creating Syncthing container for " + user + " with IP address " +
       container_ip)

network_links = []

if args.discovery_container is not None:
    network_links.append((args.discovery_container, 'discovery'))
if args.relay_container is not None:
    network_links.append((args.relay_container, 'relay'))

if len(network_links) == 0:
    network_links = None

ports = {22000: args.ports} if args.ports is not None else None

container = docker.create_container(
    image="ikogan/syncthing",
    name="syncthing-" + user,
    volumes=["/home/" + user, "/etc/localtime"],
    command=[str(uid) + ":" + str(gid)],
    environment=environment,
    host_config=docker.create_host_config(restart_policy={
        'MaximumRetryCount': 0,
        'Name': 'always'
    }, binds=[
        '/home/' + user + ':/home/syncthing:rw',
        '/etc/localtime:/etc/localtime:ro'
    ], port_bindings=ports, links=network_links)
)

docker.connect_container_to_network(container=container.get("Id"),
                                    net_id=network.get("Id"),
                                    ipv4_address=container_ip)

syslog('Starting container...')
docker.start(container=container.get('Id'))

if not args.skip_httpd:
    syslog("Configuring httpd...")
    config = open('/etc/httpd/conf.d/includes/syncthing/' + user + '.conf',
                  'w')
    print >> config, "ProxyPass /syncthing/" + user +\
        " http://" + container_ip + ":8384"
    print >> config, "ProxyPassReverse /syncthing/" + user + " http://" +\
        container_ip + ":8384"
    config.close()

    syslog('Reloading httpd...')
    if os.system('apachectl configtest') == 0:
        os.system('systemctl restart httpd')
