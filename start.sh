#!/bin/bash

set -e

export HOME="/home"

CONFIG_FOLDER="/home/.config/syncthing"
CONFIG_FILE="$CONFIG_FOLDER/config.xml"

if [ ! -f "$CONFIG_FILE" ]; then
    /usr/bin/syncthing -generate="$CONFIG_FOLDER"
fi

xmlstarlet ed -L -u "/configuration/gui/address" -v "0.0.0.0:8384" "$CONFIG_FILE"

if [[ -z "${ROLE}" || "${ROLE}" == "sync" ]]; then
    COMMAND="syncthing -no-browser"
elif [[ "${ROLE}" == "relay" ]]; then
    COMMAND="strelaysrv -keys /etc/relaysrv"
elif [[ "${ROLE}" == "discovery" ]]; then
    COMMAND="stdiscosrv"
fi

exec ${COMAND}
