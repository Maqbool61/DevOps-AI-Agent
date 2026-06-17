#!/bin/bash
# Run this script ON your EC2 instance to install Docker and start a crash-looping test app.
# Usage: curl -sL <raw-url> | bash   OR   scp to EC2 and: sudo bash ec2-docker-test-setup.sh
set -euo pipefail

echo "=== DevOps Agent E2E Test — Docker crash-loop setup ==="

# Install Docker (Amazon Linux 2023 / Ubuntu)
if command -v apt-get &>/dev/null; then
  sudo apt-get update -qq
  sudo apt-get install -y docker.io docker-compose-plugin
  sudo systemctl enable docker
  sudo systemctl start docker
  sudo usermod -aG docker "$USER" 2>/dev/null || true
elif command -v yum &>/dev/null || command -v dnf &>/dev/null; then
  sudo yum update -y -q || sudo dnf update -y -q
  sudo yum install -y docker || sudo dnf install -y docker
  sudo systemctl enable docker
  sudo systemctl start docker
  sudo usermod -aG docker "$USER" 2>/dev/null || true
else
  echo "Unsupported OS — install Docker manually"
  exit 1
fi

TEST_DIR=/opt/agent-docker-test
sudo mkdir -p "$TEST_DIR"
cd "$TEST_DIR"

# Broken app: exits immediately (simulates CrashLoop / restart loop)
sudo tee Dockerfile >/dev/null <<'EOF'
FROM alpine:3.19
# Missing required env — app exits with code 1 (fix: set REQUIRED_ENV=ok)
CMD ["sh", "-c", "echo Starting broken-app...; test -n \"$REQUIRED_ENV\" || { echo 'ERROR: REQUIRED_ENV not set'; exit 1; }; echo OK"]
EOF

sudo tee docker-compose.yml >/dev/null <<'EOF'
services:
  broken-app:
    build: .
    container_name: broken-app
    restart: unless-stopped
    # Intentionally missing: environment: REQUIRED_ENV=ok
EOF

echo "Building and starting broken container..."
sudo docker compose build -q
sudo docker compose up -d

sleep 5
echo ""
echo "=== Container status (should be Restarting or Exited) ==="
sudo docker ps -a --filter name=broken-app
echo ""
echo "=== Recent logs ==="
sudo docker logs broken-app --tail 20 2>&1 || true
echo ""
echo "=== FIX (manual) ==="
echo "  cd $TEST_DIR"
echo "  # Add to docker-compose.yml under broken-app:"
echo "  #   environment:"
echo "  #     REQUIRED_ENV: ok"
echo "  sudo docker compose up -d --build"
echo ""
echo "=== Trigger the agent (from your laptop) ==="
echo '  curl -X POST http://<AGENT_URL>:8000/webhook/manual \'
echo '    -H "Content-Type: application/json" \'
echo '    -H "X-Org-ID: acme-corp" \'
echo '    -d '"'"'{"type":"server","host":"'"$(curl -s http://169.254.169.254/latest/meta-data/public-hostname 2>/dev/null || hostname)"'","description":"Docker container broken-app keeps restarting","service":"broken-app"}'"'"
