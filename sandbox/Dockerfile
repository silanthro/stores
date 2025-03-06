FROM docker.io/ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV DEBIAN_PRIORITY=high

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.5.6 /uv /uvx /bin/

RUN apt-get update && \
    apt-get -y upgrade && \
    apt-get -y install \
    # UI Requirements
    xvfb \
    xterm \
    xdotool \
    scrot \
    imagemagick \
    sudo \
    mutter \
    x11vnc \
    # Python/pyenv reqs
    build-essential \
    libssl-dev  \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    curl \
    git \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev \
    # Network tools
    net-tools \
    netcat \
    # PPA req
    software-properties-common && \
    # Userland apps
    sudo add-apt-repository ppa:mozillateam/ppa && \
    sudo apt-get install -y --no-install-recommends \
    libreoffice \
    firefox-esr \
    x11-apps \
    xpdf \
    gedit \
    xpaint \
    tint2 \
    galculator \
    pcmanfm \
    xclip \
    unzip && \
    apt-get clean

ARG DISPLAY_NUM=1
ARG HEIGHT=768
ARG WIDTH=1024
ENV DISPLAY_NUM=$DISPLAY_NUM
ENV HEIGHT=$HEIGHT
ENV WIDTH=$WIDTH

# setup user
ENV USERNAME=computeruse
ENV HOME=/home/$USERNAME
WORKDIR $HOME
RUN useradd -m -s /bin/bash -d $HOME $USERNAME
RUN echo "${USERNAME} ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers
RUN chown -R computeruse $HOME

USER computeruse

# Create shared directory
# RUN mkdir ./shared

# Install server requirements
COPY ./sandbox/pyproject.toml pyproject.toml
RUN uv sync

# Copy other files
COPY --chown=$USERNAME ./sandbox/launch ./launch
COPY --chown=$USERNAME ./sandbox/tools ./tools

ENTRYPOINT [ "./launch/entrypoint.sh" ]
