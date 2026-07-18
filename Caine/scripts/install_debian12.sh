#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root" >&2
  exit 1
fi

install -d -o caine -g caine /var/lib/caine /var/log/caine
install -d /etc/caine
install -m 0644 Caine/config/caine.yaml /etc/caine/caine.yaml
install -m 0644 Caine/systemd/caine.service /etc/systemd/system/caine.service

python3.12 -m pip install -r requirements.txt
systemctl daemon-reload
systemctl enable caine.service
systemctl restart caine.service

