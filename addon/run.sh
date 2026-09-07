#!/usr/bin/with-contenv bashio
# Thin reverse-proxy into alarm-core's web UI/API, running on the
# separate NVR/AI host. Does not run any of the actual workload — see
# docs/architecture.md in the main repo.

set -e

ALARM_CORE_URL=$(bashio::config 'alarm_core_url')
AUTH_TOKEN=$(bashio::config 'auth_token')

bashio::log.info "Proxying ingress to alarm-core at ${ALARM_CORE_URL}"

cat > /etc/nginx/nginx.conf <<EOF
worker_processes 1;
events { worker_connections 1024; }
http {
    server {
        listen 8091;
        location / {
            proxy_pass ${ALARM_CORE_URL}/;
            proxy_set_header Authorization "Bearer ${AUTH_TOKEN}";
            proxy_set_header Host \$host;
        }
    }
}
EOF

exec nginx -g "daemon off;"
