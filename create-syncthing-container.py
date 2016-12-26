#!/usr/bin/python

# This script is unnecessary complicated as it went through several
# evolutions before getting to this point. It supports creating
# Syncthing containers:
#
# - On the command line.
# - As a WSGI application.
# - As a simple REST call.
#
# Generally, the point is to create a syncthing container, add it
# to the appropriate network, and update httpd so it proxies to the
# new container.
import os
import sys
import argparse
import docker as Docker
from pwd import getpwnam
from syslog import syslog
from flask import Flask, jsonify, request
from logging.handlers import SysLogHandler

truthy = ['true', 'yes']


class ContainerAlreadyExistsError(Exception):
    def __init__(self, user):
        super(ContainerAlreadyExistsError, self).\
            __init__("Syncthing container for", user, "already exists.")


class IPRangeExhaustedError(Exception):
    def __init__(self):
        super(IPRangeExhaustedError, self).\
            __init__("No IP Addresses remaining in network for new container.")


class ApacheConfigurationFailedError(Exception):
    pass


class SyncthingOptions(object):
    """All of the various options for containers."""
    def __init__(self):
        self.user = None                 # The user owning the container
        self.disable_upnp = False        # Whether or not UPnP should be used
        self.discovery = None            # Discovery server IP
        self.relay = None                # Relay server IP
        self.disable_relay = False       # Disable relaying entirely
        self.discovery_container = None  # Discovery container name
        self.relay_container = None      # Relay container name
        self.skip_httpd = False          # Do or do not update the httpd config
        self.ports = None                # Port range to use
        self.api = None                  # Start a REST API on this port


def create_container(args):
    """Peform the actual container creation. See SyncthingOptions
    for options."""
    if not args.user:
        print >> sys.stderr, "A user for whom to create the container is",
        "required."
        sys.exit(1)

    user = args.user[0]
    docker = Docker.Client(base_url='unix://var/run/docker.sock')

    try:
        uid = getpwnam(user).pw_uid
        gid = getpwnam(user).pw_gid
    except Exception, e:
        raise Exception("Error loading user " + args.user + ": " + str(e))

    try:
        container = docker.inspect_container("syncthing-" + user)
        raise ContainerAlreadyExistsError(user)
    except Docker.errors.NotFound:
        pass

    container_ip = None
    try:
        # Find an IP address for this new container on the network
        network = docker.inspect_network("syncthing")

        for octet in range(10, 250):
            exists = False
            for c in network['Containers'].values():
                if c['IPv4Address'] == "172.18.1." + str(octet) + "/24":
                    exists = True
                    break
            if not exists:
                container_ip = "172.18.1." + str(octet)
                break

        if container_ip is None:
            raise IPRangeExhaustedError()
    except Docker.errors.NotFound:
        # Create the network and assign the first IP to this container
        syslog("Creating syncthing network...")
        ipam = Docker.utils.create_ipam_config(
            pool_configs=[
                Docker.utils.create_ipam_pool(subnet='172.18.1.0/24')]
        )
        network = docker.create_network("syncthing", driver="bridge",
                                        ipam=ipam)
        container_ip = '172.18.1.10'

    # Setup all the environment variables our container will need
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
        # Create a proxy file for httpd
        syslog("Configuring httpd...")
        config = open('/etc/httpd/conf.d/syncthing/' + user + '.conf', 'w')
        print >> config, "ProxyPass /syncthing/" + user +\
            " http://" + container_ip + ":8384"
        print >> config, "ProxyPassReverse /syncthing/" + user + " http://" +\
            container_ip + ":8384"
        config.close()

        # Restart httpd using systemctl, needs improvement.
        syslog('Reloading httpd...')
        os.system('systemctl httpd restart')


def api(args):
    """Host an API with Flask that'll pull the various options out of httpd
    headers and call create_container."""
    app = Flask(__name__)

    @app.route('/', methods=['POST'])
    def api():
        headers = request.headers

        if 'x-remote-user' not in headers:
            return jsonify(error="Authentication Required"), 507

        args = SyncthingOptions()
        args.user = [headers['x-remote-user']]

        args.disable_upnp = True if 'x-st-disable-upnp' in headers and \
            headers['x-st-disable-upnp'].lower() in truthy else False
        args.discovery = headers['x-st-discovery'] if 'st_discovery' \
            in headers else None
        args.relay = headers['x-st-relay'] if 'x-st-relay' in headers else None
        args.disable_relay = True if 'x-st-disable-relay' in headers and \
            headers['x-st-disable-relay'].lower() in truthy else False
        args.discovery_container = headers['x-st-discovery-container'] \
            if 'x-st-discovery-container' in headers else None
        args.relay_container = headers['x-st-relay-container'] \
            if 'x-st-relay-container' in headers else None
        args.skip_httpd = True if 'x-st-skip-httpd-config' in headers and \
            headers['x-st-skip-httpd-config'].lower() in truthy else False
        args.ports = headers['x-st-expose'] if 'x-st-expose' in headers \
            else None

        try:
            create_container(args)
            return (jsonify(message="Container created."), 201)
        except ContainerAlreadyExistsError, e:
            return (jsonify(message=str(e)), 409)
        except IPRangeExhaustedError, e:
            return (jsonify(message=str(e)), 507)
        except ApacheConfigurationFailedError, e:
            return (jsonify(message="Unable to complete web server " +
                            "configuration: " + str(e)), 500)
        except Exception, e:
            return (jsonify(message=str(e)), 500)

    logHandler = SysLogHandler()
    app.logger.addHandler(logHandler)
    app.run(port=int(args.api))


def application(environ, start_response):
    """Define a WSGI application handler that'll pull the options out
    of the environment and call create_container."""
    args = SyncthingOptions()

    if 'REMOTE_USER' in environ:
        args.user = [environ['REMOTE_USER']]

        args.disable_upnp = True if 'ST_DISABLE_UPNP' in environ and \
            environ['ST_DISABLE_UPNP'].lower() in truthy else False
        args.discovery = environ['ST_DISCOVERY'] if 'ST_DISCOVERY' \
            in environ else None
        args.relay = environ['ST_RELAY'] if 'ST_RELAY' in environ else None
        args.disable_relay = True if 'ST_DISABLE_RELAY' in environ and \
            environ['ST_DISABLE_RELAY'].lower() in truthy else False
        args.discovery_container = environ['ST_DISCOVERY_CONTAINER'] \
            if 'ST_DISCOVERY_CONTAINER' in environ else None
        args.relay_container = environ['ST_RELAY_CONTAINER'] \
            if 'ST_RELAY_CONTAINER' in environ else None
        args.skip_httpd = True if 'ST_SKIP_HTTPD_CONFIG' in environ and \
            environ['ST_SKIP_HTTPD_CONFIG'].lower() in truthy else False
        args.ports = environ['ST_EXPOSE'] if 'ST_EXPOSE' in environ else None

        try:
            create_container(args)
            status = '201 Created'
            output = '{ "message": "Container created." }'
        except ContainerAlreadyExistsError, e:
            status = '409 Conflict'
            output = '{ "message": "' + str(e).replace('"', '\\"') + '" }'
        except IPRangeExhaustedError, e:
            status = '507 Insufficient Storage'
            output = '{ "message": "' + str(e).replace('"', '\\"') + '" }'
        except ApacheConfigurationFailedError, e:
            status = '500 Internal Server Error'
            output = '{ "message": "Unable to complete web server ' +\
                'configuration: ' + str(e).replace('"', '\\"') + '" }'
        except Exception, e:
            status = '500 Internal Server Error'
            output = '{ "message": "' + str(e).replace('"', '\\"') + '" }'
    else:
        status = 401
        output = '{ "message": "Authorization Required" }'

    response_headers = [('Content-type', 'application/json'),
                        ('Content-Length', str(len(output)))]
    start_response(status, response_headers)

    return [output]

if __name__ == '__main__':
    # If we're run from the command line, parse arguments and decide
    # whether or not we're hosting an API or just creating a container.
    parser = argparse.ArgumentParser(description='Create a Syncthing ' +
                                     'Docker container for a given user.')
    parser.add_argument('--disable-upnp', dest='disable_upnp',
                        action='store_true', help='Disable UPnP Port ' +
                        'Mapping')
    parser.add_argument('--relay', dest='relay', action='store',
                        help='Relay server address.')
    parser.add_argument('--relay-container', dest='relay_container',
                        action='store', help='Container hosting the ' +
                        'relay in case linkage between containers is ' +
                        'necessary.')
    parser.add_argument('--disable-relaying', dest='disable_relay',
                        action='store_true',
                        help='Disable relaying entirely.')
    parser.add_argument('--discovery', dest='discovery', action='store',
                        help='Discovery server address.')
    parser.add_argument('--discovery-container',
                        dest='discovery_container',
                        action='store',
                        help='Container hosting the discovery server ' +
                        'in case linkage between containers is necessary.')
    parser.add_argument('--skip-httpd', dest='skip_httpd',
                        action='store_true',
                        help='Skip creating an httpd configuration.')
    parser.add_argument('--expose', dest='ports', action='store',
                        help='Expose a range of ports for the ST ' +
                        'protocol.')
    parser.add_argument('--api-port', dest='api', action='store',
                        help='Start an API server that can create containers.')
    parser.add_argument('user', nargs='?', default=None)

    args = SyncthingOptions()
    parser.parse_args(namespace=args)

    if args.api:
        api(args)
    else:
        create_container(args)
