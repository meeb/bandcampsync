#!/bin/bash

# Set the 'app' user UID and GID from the ENV vars
PUID="${PUID:-1000}"
PUID="${PUID:-1000}"
groupmod -o -g "$PGID" app
usermod -o -u "$PUID" app
echo "Set service UID:GID to ${PUID}:${PGID}"

# Execute whatever is set in CMD
exec "$@"
