#!/bin/bash
set  -e

VERSION=`curl -s https://api.github.com/repos/syncthing/syncthing/releases/latest | jq -r '.tag_name'`

mkdir -p /go/src/github.com/syncthing
cd /go/src/github.com/syncthing
git clone https://github.com/syncthing/syncthing.git
cd syncthing
git checkout ${VERSION}
go run build.go
mv bin/* /usr/bin

VERSION=`curl -s https://api.github.com/repos/syncthing/syncthing-inotify/releases/latest | jq -r '.tag_name'`
mkdir -p /go/src/github.com/syncthing-inotify
cd /go/src/github.com/syncthing-inotify
git clone https://github.com/syncthing/syncthing-inotify.git
cd syncthing-inotify
git checkout ${VERSION}
go get
go build
mv syncthing-inotify /usr/bin/syncthing-inotify

rm -Rf /go/src/github.com
