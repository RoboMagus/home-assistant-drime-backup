#!/usr/bin/env bash
set -e

apk update && apk add --no-cache git wget

pip install -r requirements.txt

hass -c config --script ensure_config

# Install HACS
if [ ! -d "config/custom_components/hacs" ]; then
    mkdir -p config/custom_components/hacs
    echo "Downloading HACS"
    wget "https://github.com/hacs/integration/releases/latest/download/hacs.zip" -O hacs.zip
    unzip hacs.zip -d config/custom_components/hacs >/dev/null 2>&1
    rm hacs.zip
fi
