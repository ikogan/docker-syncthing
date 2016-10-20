#!/bin/bash
docker create --name=syncthing-relay --restart=always \
  -v /etc/localtime:/etc/localtime:ro \
  -v /data/Docker/etc/syncthing/relay:/etc/syncthing/relay \
  -e ROLE=relay -p 22070:22070 -p 22067:20067 \
  ikogan/syncthing
