#!/bin/bash
docker create --name=syncthing-discovery --restart=always \
  -v /etc/localtime:/etc/localtime:ro \
  -v /etc/pki/tls/certs/http.crt:/etc/syncthing/discovery/cert.pem:ro \
  -v /etc/pki/tls/private/http.key:/etc/syncthing/discovery/key.pem:ro \
  -p 28443:8443 \
  -e ROLE=discovery ikogan/syncthing
