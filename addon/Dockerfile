ARG BUILD_FROM=ghcr.io/hassio-addons/base:15.0.6
FROM ${BUILD_FROM}

RUN apk add --no-cache nginx

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
