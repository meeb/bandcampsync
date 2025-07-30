FROM debian:bookworm-slim

ARG REPOSITORY="meeb/bandcampsync"
ARG VERSION="v0.5.3"

ENV DEBIAN_FRONTEND="noninteractive" \
  HOME="/root" \
  LANGUAGE="en_US.UTF-8" \
  LANG="en_US.UTF-8" \
  LC_ALL="en_US.UTF-8" \
  TERM="xterm"

# Set up the container
RUN set -x && \
  apt-get update && \
  # Set locale
  apt-get -y --no-install-recommends install locales && \
  echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
  locale-gen en_US.UTF-8 && \
  # Install required distro packages
  apt-get -y --no-install-recommends install \
    git \
    gosu \
    python3 \
    python3-dev \
    python3-pip && \
  # Create a 'app' user which the service will run as
  groupadd app && \
  useradd -M -d /app -s /bin/false -g app app && \
  # Clean up
  apt-get -y autoremove && \
  apt-get -y autoclean && \
  rm -rf /var/lib/apt/lists/* && \
  rm -rf /var/cache/apt/* && \
  rm -rf /tmp/

RUN set -x && \
  # Allow root to use sudo
  echo "root  ALL = NOPASSWD: /bin/su ALL" >> /etc/sudoers && \
  # Install BandcampSync
  python3 -m pip install --break-system-packages git+https://github.com/${REPOSITORY}.git@${VERSION}#egg=bandcampsync

# Volumes
VOLUME ["/config", "/downloads"]

# Set the 'app' user UID and GID in the entrypoint
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

# Run the service
CMD ["bandcampsync-service"]
