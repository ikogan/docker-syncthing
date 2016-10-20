ikogan/syncthing
===================

[Syncthing](http://syncthing.net/) Docker image that includes relaying and discovery.

This image is designed to enable running both a simple Syncthing container
as well as a relay or discovery server. It also contains scripts that simplify
creating a series of containers for multiple users behind a reverse proxy.

Check out the included scripts for details on how to run these containers.
Specifying a port range to `create-syncthing.py` using the `--expose` argument
will easily allow managing multiple user containers. The script will also create
a reverse proxy config for httpd that must be included from a `<Location>`
entry in an httpd configuration.

