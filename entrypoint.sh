#!/bin/bash

PUID="${PUID:-1000}"
PUID="${PUID:-1000}"

# Set the 'app' user UID and GID from the ENV vars
groupmod -o -g "$PGID" app
usermod -o -u "$PUID" app

echo "Set service UID:GID to ${PUID}:${PGID}"
