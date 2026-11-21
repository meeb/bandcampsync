FROM debian:trixie-slim

ARG REPOSITORY="meeb/bandcampsync"
ARG VERSION="main"

ENV DEBIAN_FRONTEND="noninteractive" \
  HOME="/root" \
  LANGUAGE="en_US.UTF-8" \
  LANG="en_US.UTF-8" \
  LC_ALL="en_US.UTF-8" \
  TERM="xterm" \
  UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy \
  UV_NO_CACHE=1 \
  UV_PYTHON_DOWNLOADS=never \
  UV_PROJECT_ENVIRONMENT="/opt/bandcampsync" \
  PATH="/opt/bandcampsync/bin:${PATH}"

COPY --from=ghcr.io/astral-sh/uv:0.13.9@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d /uv /usr/local/bin/uv

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
    python3-dev && \
  # Create a 'app' user which the service will run as
  groupadd app && \
  useradd -M -d /app -s /bin/false -g app app && \
  # Clean up
  apt-get -y autoremove && \
  apt-get -y autoclean && \
  rm -rf /var/lib/apt/lists/* && \
  rm -rf /var/cache/apt/* && \
  rm -rf /tmp/*

RUN set -x && \
  # Allow root to use sudo
  echo "root  ALL = NOPASSWD: /bin/su ALL" >> /etc/sudoers && \
  # Install BandcampSync
  git clone https://github.com/${REPOSITORY}.git /tmp/bandcampsync && \
  git -C /tmp/bandcampsync checkout "${VERSION}" && \
  uv sync --project /tmp/bandcampsync --locked --no-dev --no-editable --python /usr/bin/python3 && \
  rm -rf /tmp/bandcampsync

# Volumes
VOLUME ["/config", "/downloads"]

# Set the 'app' user UID and GID in the entrypoint
COPY entrypoint.sh /entrypoint.sh
COPY ignores.template.txt /ignores.template.txt
ENTRYPOINT ["/entrypoint.sh"]

# Run the service
CMD ["bandcampsync-service"]
