FROM golang:1.9
MAINTAINER Ilya Kogan <ikogan@mythicnet.org>

ENV GOSU_VERSION 1.9
ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && \
    apt-get install -y git curl jq xmlstarlet wget ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN dpkgArch="$(dpkg --print-architecture | awk -F- '{ print $NF }')" \
    && wget -O /usr/local/bin/gosu "https://github.com/tianon/gosu/releases/download/$GOSU_VERSION/gosu-$dpkgArch" \
    && wget -O /usr/local/bin/gosu.asc "https://github.com/tianon/gosu/releases/download/$GOSU_VERSION/gosu-$dpkgArch.asc" \
    && export GNUPGHOME="$(mktemp -d)" \
    && gpg --keyserver ha.pool.sks-keyservers.net --recv-keys B42F6819007F00F88E364FD4036A9C25BF357DD4 \
    && gpg --batch --verify /usr/local/bin/gosu.asc /usr/local/bin/gosu \
    && rm -r "$GNUPGHOME" /usr/local/bin/gosu.asc \
    && chmod +x /usr/local/bin/gosu \
    && gosu nobody true

ADD docker/build.sh /build.sh
RUN chmod +x /build.sh

ADD docker/start.sh /start.sh
RUN chmod +x /start.sh

ARG SYNCTHING_VERSION
ARG SYNCTHING_INOTIFY_VERSION

ENV SYNCTHING_VERSION=${SYNCTHING_VERSION}
ENV SYNCTHING_INOTIFY_VERSION=${SYNCTHING_INOTIFY_VERSION}

RUN /build.sh

VOLUME ["/home/syncthing"]

EXPOSE 8384 8443 22000 21027/udp 22067 22070

ENTRYPOINT ["/start.sh"]
