FROM golang:1.6.2
MAINTAINER Ilya Stepanov <dev@ilyastepanov.com>

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && \
    apt-get install -y git curl jq xmlstarlet && \
    rm -rf /var/lib/apt/lists/*

ADD build.sh /build.sh
RUN chmod +x /build.sh

ARG ROLE
RUN /build.sh

ADD start.sh /start.sh
RUN chmod +x /start.sh

VOLUME ["/home/.config/syncthing"]

EXPOSE 8384 22000 21027/udp

CMD ["/start.sh", "${ROLE}"]
