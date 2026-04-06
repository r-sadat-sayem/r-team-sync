#!/bin/sh
set -eu

escape_js() {
  printf '%s' "${1:-}" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

chat_url=$(escape_js "${N8N_CHAT_URL:-}")
demo_title=$(escape_js "${DEMO_TITLE:-TeamSync AI}")
demo_badge=$(escape_js "${DEMO_BADGE:-Public Review Build}")
n8n_upstream_base="${N8N_UPSTREAM_BASE:-http://host.docker.internal:5678}"

cat > /usr/share/nginx/html/config.js <<EOF
window.__TEAMSYNC_CONFIG__ = {
  N8N_CHAT_URL: "${chat_url}",
  DEMO_TITLE: "${demo_title}",
  DEMO_BADGE: "${demo_badge}"
};
EOF

cat > /etc/nginx/conf.d/default.conf <<EOF
server {
    listen 4040;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    location = /healthz {
        access_log off;
        add_header Content-Type text/plain;
        return 200 'ok';
    }

    location /webhook/ {
        proxy_pass ${n8n_upstream_base};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
