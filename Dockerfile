FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND="noninteractive" \
  HOME="/root" \
  LANGUAGE="en_US.UTF-8" \
  LANG="en_US.UTF-8" \
  LC_ALL="en_US.UTF-8" \
  TERM="xterm"

# Set up the container
RUN set -x && \
  apt-get update && \
  # Install required distro packages
  apt-get -y --no-install-recommends install \
    python3 \
    python3-dev \
    python3-pip && \
  # Install app
  python -m pip install git+https://github.com/meeb/bandcampsync.git && \
  # Create a 'app' user which the service will run as
  groupadd app && \
  useradd -M -d /app -s /bin/false -g app app && \
  # Clean up
  apt-get -y autoremove && \
  apt-get -y autoclean && \
  rm -rf /var/lib/apt/lists/* && \
  rm -rf /var/cache/apt/* && \
  rm -rf /tmp/

# Volumes
VOLUME ["/config", "/downloads"]

# Set the 'app' user UID and GID in the entrypoint
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

# Drop to the 'app' user
USER app

# Run the service
CMD ["bandcampsync-service"]
