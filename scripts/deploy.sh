#!/usr/bin/env bash
# Push local artefacts to EC2 and restart the stack.
# Run from WSL, Git Bash, or any POSIX shell on Windows.
#
# Required env vars:
#   EC2_HOST  — EC2 public IP or DNS name
#   EC2_KEY   — path to the .pem key file (default: ~/.ssh/airbnb-intel.pem)
#   EC2_USER  — SSH user (default: ec2-user for Amazon Linux)
#
# Example:
#   EC2_HOST=54.123.45.67 EC2_KEY=~/.ssh/airbnb-intel.pem ./scripts/deploy.sh

set -euo pipefail

EC2_HOST="${EC2_HOST:?Set EC2_HOST to your instance public IP or DNS}"
EC2_USER="${EC2_USER:-ec2-user}"
KEY="${EC2_KEY:-$HOME/.ssh/airbnb-intel.pem}"
REMOTE=/home/ec2-user/airbnb-intel
SSH="ssh -i $KEY -o StrictHostKeyChecking=no"

echo "=== Syncing artefacts to $EC2_USER@$EC2_HOST:$REMOTE ==="
# data/ is excluded — the API reads from reports/tables/ (pre-built artefacts).
# Raw CSVs are not needed at runtime and would be slow to transfer.
rsync -az --progress \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.venv/' \
  --exclude 'dashboard/node_modules/' \
  --exclude 'dashboard/dist/' \
  --exclude '.git/' \
  --exclude 'reports/figures/' \
  --exclude 'reports/ge_validation/' \
  --exclude 'reports/llm_summaries/' \
  --exclude '*.parquet' \
  -e "ssh -i $KEY -o StrictHostKeyChecking=no" \
  src/ dashboard/ config/ reports/ models/ \
  Dockerfile.api Dockerfile.dashboard \
  docker-compose.yml docker-compose.cloud.yml \
  nginx.conf requirements.txt \
  "$EC2_USER@$EC2_HOST:$REMOTE/"

echo "=== Uploading .env (never committed to git) ==="
scp -i "$KEY" -o StrictHostKeyChecking=no \
  .env "$EC2_USER@$EC2_HOST:$REMOTE/.env"

echo "=== Building and starting containers on EC2 ==="
$SSH "$EC2_USER@$EC2_HOST" \
  "cd $REMOTE && DOCKER_BUILDKIT=1 docker compose -f docker-compose.yml -f docker-compose.cloud.yml up -d --build"

echo ""
echo "=== Deployment complete ==="
echo "    Dashboard : http://$EC2_HOST"
echo "    API health: http://$EC2_HOST/api/health"
