#!/bin/bash
set -e

if [[ ! -z "${2}" ]]; then
    USERSPEC=(${2//\:/ })
    ROLE="${1}"
else
    USERSPEC=(${1//\:/ })
fi

if [[ -z "${ROLE}" || "${ROLE}" == "sync" ]]; then
    if [[ -z "${SYNCTHING_HOME}" ]]; then
        export HOME="/home/syncthing"
    else
        export HOME="${SYNCTHING_HOME}"
    fi

    if [[ -z "${1}" ]]; then
        echo "Please specify user to run as with 'user:group' as first argument." >&2; exit 1
    fi

    USER="${USERSPEC[0]}"
    GROUP="${USERSPEC[1]}"

    if [[ -z '${USER}' || -z '${GROUP}' ]]; then
        echo "Unable to parse user specification ${USERSPEC}." >&2; exit 1
    fi

    integer='^[0-9]+$'
    if ! [[ ${USER} =~ ${integer} ]] ; then
        echo "Error: User must be a number" >&2; exit 1
    fi

    if ! [[ ${GROUP} =~ ${integer} ]]; then
        echo "Error: Group must be a number" >&2; exit 1
    fi

    CONFIG_FOLDER="${HOME}/.config/syncthing"
    CONFIG_FILE="$CONFIG_FOLDER/config.xml"

    if [ -z "$(getent group ${GROUP} || true)" ]; then
        echo "Creating group syncthing with id ${GROUP}..."
        groupadd --gid ${GROUP} syncthing
    fi

    if [ -z "$(getent passwd ${USER} || true)" ]; then
        echo "Creating user syncthing with id ${USER} and gid ${GROUP}..."
        useradd -M --uid ${USER} --gid ${GROUP} --home "${HOME}" syncthing
    fi

    chown ${USER}:${USER} /opt/syncthing
    if [[ -d "${CONFIG_FOLDER}" ]]; then
        chown -R ${USER}:${GROUP} ${CONFIG_FOLDER}
    fi

    if [ ! -f "$CONFIG_FILE" ]; then
        echo "Generating syncthing configuration..."
        gosu ${USER} /opt/syncthing/syncthing -generate="$CONFIG_FOLDER"
    fi

    xmlstarlet ed -L -u "/configuration/gui/address" -v "0.0.0.0:8384" "${CONFIG_FILE}"
    xmlstarlet ed -L -u "/configuration/gui/insecureAdminAccess" -v "true" "${CONFIG_FILE}"
    xmlstarlet ed -L -u "/configuration/options/listenAddress" -v "tcp://:22000" "${CONFIG_FILE}"
    xmlstarlet ed -L -u "/configuration/options/startBrowser" -v "false" "${CONFIG_FILE}"

    function insert_or_update() {
        if [[ -z "$(xmlstarlet sel -t -v ${1}/${2} ${CONFIG_FILE})" ]]; then
            xmlstarlet ed -L -s "${1}" -t elem -n "${2}" -v "${3}" "${CONFIG_FILE}"
        else
            xmlstarlet ed -L -u "${1}/${2}" -v "${3}" "${CONFIG_FILE}"
        fi
    }

    if [[ ! -z "${DISCOVERY_SERVER}" ]]; then
        echo "Setting discovery server to ${DISCOVERY_SERVER}..."
        insert_or_update "/configuration/options" "globalAnnounceServer" "${DISCOVERY_SERVER}"
    fi

    if [[ ! -z "${RELAY_SERVER}" ]]; then
        echo "Setting relay server to ${RELAY_SERVER}..."
        insert_or_update "/configuration/options" "relayServer" "${RELAY_SERVER}"
    fi

    if [[ ! -z "${DISABLE_UPNP}" ]]; then
        echo "Disabling UPNP..."
        insert_or_update "/configuration/options" "natEnabled" "false"
    fi

    if [[ ! -z "${DISABLE_RELAY}" ]]; then
        echo "Disabling relaying..."
        insert_or_update "/configuration/options" "relaysEnabled" "false"
    fi

    COMMAND="gosu ${USER} /opt/syncthing/syncthing -no-restart"
elif [[ "${ROLE}" == "relay" ]]; then
    COMMAND="/opt/syncthing/strelaysrv -keys /etc/syncthing/relay -pools=''"
elif [[ "${ROLE}" == "discovery" ]]; then
    COMMAND="/opt/syncthing/stdiscosrv"

    if [[ "${ST_SSL_ENABLED}" == "false" || "${ST_SSL_ENABLED}" == "no" ]]; then
        COMMAND="${COMMAND} -http"
    else
        COMMAND="${COMMAND} -cert=/etc/syncthing/discovery/cert.pem -key=/etc/syncthing/discovery/key.pem"
    fi
fi

exec ${COMMAND}
