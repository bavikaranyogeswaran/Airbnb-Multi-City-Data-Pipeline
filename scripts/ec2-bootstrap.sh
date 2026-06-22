#!/usr/bin/env bash
# Run once on a fresh Amazon Linux 2023 t3.micro instance.
# Installs Docker Engine + Compose plugin and creates the project directory.
#
# Usage (paste into the EC2 terminal after SSH):
#   bash <(curl -s <URL>) -- or just copy-paste the whole file

set -euo pipefail

echo "=== Installing Docker ==="
dnf update -y
dnf install -y docker
systemctl enable --now docker
usermod -aG docker ec2-user

echo "=== Installing Docker Compose plugin ==="
COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest \
    | grep '"tag_name"' | cut -d'"' -f4)
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
     -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

echo "=== Creating project directory ==="
mkdir -p /home/ec2-user/airbnb-intel/{data,reports,models,logs}

echo "=== Done ==="
echo "Log out and back in (or run 'newgrp docker') for group membership to take effect."
docker --version
docker compose version
