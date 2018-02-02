#!/bin/bash
set -e

if [[ -z "${SYNCTHING_VERSION}" ]]; then
    VERSION=`curl -s https://api.github.com/repos/syncthing/syncthing/releases/latest | jq -r '.tag_name'`
else
    VERSION=${SYNCTHING_VERSION}
fi

mkdir -p /go/src/github.com/syncthing
cd /go/src/github.com/syncthing
git clone https://github.com/syncthing/syncthing.git
cd syncthing
git checkout ${VERSION}
go run build.go
mkdir -p /opt/syncthing
mv bin/* /opt/syncthing

if [[ -z "${SYNCTHING_INOTIFY_VERSION}" ]]; then
    VERSION=`curl -s https://api.github.com/repos/syncthing/syncthing-inotify/releases/latest | jq -r '.tag_name'`
else
    VERSION=${SYNCTHING_INOTIFY_VERSION}
fi

mkdir -p /go/src/github.com/syncthing-inotify
cd /go/src/github.com/syncthing-inotify
git clone https://github.com/syncthing/syncthing-inotify.git
cd syncthing-inotify
git checkout ${VERSION}
go get
go build
mv syncthing-inotify /opt/syncthing/syncthing-inotify

rm -Rf /go/src/github.com
