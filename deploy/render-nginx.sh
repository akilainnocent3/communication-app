#!/bin/sh
# Render the Nginx templates for this server and test the result.
#   sudo CM_DOMAIN=admin.example.co.tz deploy/render-nginx.sh          # admin (and phone) domain
#   sudo CM_API_DOMAIN=api.example.co.tz deploy/render-nginx.sh api    # optional phone-only domain
# Only ${CM_DOMAIN} / ${CM_API_DOMAIN} are substituted; Nginx's own $variables stay as they are.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
target=${NGINX_SITES:-/etc/nginx/sites-available}
if [ "${1:-admin}" = "api" ]; then
  : "${CM_API_DOMAIN:?set CM_API_DOMAIN}"
  envsubst '${CM_API_DOMAIN}' < "$here/nginx-api.conf.template" > "$target/communication-manager-api"
  echo "wrote $target/communication-manager-api"
else
  : "${CM_DOMAIN:?set CM_DOMAIN}"
  envsubst '${CM_DOMAIN}' < "$here/nginx.conf.template" > "$target/communication-manager"
  echo "wrote $target/communication-manager"
fi
if command -v nginx >/dev/null 2>&1; then nginx -t; fi
