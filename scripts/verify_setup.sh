#!/bin/bash

# DevOps AI Agent - Setup Verification Script
# This script verifies that the agent is properly configured

set -e

echo "🔍 DevOps AI Agent - Setup Verification"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track errors
ERRORS=0
WARNINGS=0

# Check function
check() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $1"
    else
        echo -e "${RED}✗${NC} $1"
        ((ERRORS++))
    fi
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

# 1. Check Python version
echo "📦 Checking Dependencies..."
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 9 ]; then
    check "Python $PYTHON_VERSION (requires 3.9+)"
else
    echo -e "${RED}✗${NC} Python version $PYTHON_VERSION is too old (requires 3.9+)"
    ((ERRORS++))
fi

# 2. Check virtual environment
if [ -n "$VIRTUAL_ENV" ]; then
    check "Virtual environment activated"
else
    warn "Virtual environment not activated (recommended: source venv/bin/activate)"
fi

# 3. Check Python packages
echo ""
echo "📚 Checking Python Packages..."

check_package() {
    python -c "import $1" 2>/dev/null
    check "$1"
}

check_package "anthropic"
check_package "fastapi"
check_package "uvicorn"

# Optional packages
python -c "import kubernetes" 2>/dev/null
if [ $? -eq 0 ]; then
    check "kubernetes (optional)"
else
    warn "kubernetes package not installed (needed for K8s features)"
fi

python -c "import boto3" 2>/dev/null
if [ $? -eq 0 ]; then
    check "boto3 (optional - AWS)"
else
    warn "boto3 not installed (needed for AWS features)"
fi

# 4. Check configuration files
echo ""
echo "📄 Checking Configuration Files..."

if [ -f ".env" ]; then
    check ".env file exists"
    
    # Check for required variables
    if grep -q "ANTHROPIC_API_KEY=" .env && ! grep -q "ANTHROPIC_API_KEY=$" .env; then
        check "ANTHROPIC_API_KEY is set"
    else
        echo -e "${RED}✗${NC} ANTHROPIC_API_KEY not configured in .env"
        ((ERRORS++))
    fi
    
    if grep -q "SLACK_WEBHOOK_URL=" .env && ! grep -q "SLACK_WEBHOOK_URL=$" .env; then
        check "SLACK_WEBHOOK_URL is set"
    else
        warn "SLACK_WEBHOOK_URL not configured (notifications won't work)"
    fi
    
    if grep -q "GITHUB_TOKEN=" .env && ! grep -q "GITHUB_TOKEN=$" .env; then
        check "GITHUB_TOKEN is set"
    else
        warn "GITHUB_TOKEN not configured (GitHub features won't work)"
    fi
    
else
    echo -e "${RED}✗${NC} .env file not found (copy from .env.example)"
    ((ERRORS++))
fi

# 5. Check project structure
echo ""
echo "📁 Checking Project Structure..."

check_dir() {
    if [ -d "$1" ]; then
        check "$1/ directory exists"
    else
        echo -e "${RED}✗${NC} $1/ directory missing"
        ((ERRORS++))
    fi
}

check_dir "agent"
check_dir "api"
check_dir "collectors"
check_dir "tools"
check_dir "k8s"
check_dir "tests"

# 6. Check Git setup
echo ""
echo "🔧 Checking Git Configuration..."

if [ -d ".git" ]; then
    check "Git repository initialized"
    
    # Check for remote
    if git remote -v | grep -q origin; then
        REMOTE=$(git remote get-url origin)
        check "Git remote configured: $REMOTE"
    else
        warn "No git remote configured (run: git remote add origin YOUR_REPO_URL)"
    fi
else
    echo -e "${RED}✗${NC} Not a git repository"
    ((ERRORS++))
fi

# 7. Check Kubernetes access (if applicable)
echo ""
echo "☸️  Checking Kubernetes Access..."

if command -v kubectl &> /dev/null; then
    check "kubectl is installed"
    
    if kubectl cluster-info &> /dev/null; then
        check "kubectl can connect to cluster"
        
        CONTEXT=$(kubectl config current-context)
        check "Current context: $CONTEXT"
    else
        warn "kubectl cannot connect to cluster (K8s features won't work)"
    fi
else
    warn "kubectl not installed (needed for K8s features)"
fi

# 8. Test API server startup
echo ""
echo "🚀 Testing API Server..."

# Check if server is already running
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    warn "Port 8000 is already in use (server might be running)"
else
    echo "Starting API server for quick test..."
    
    # Start server in background with timeout
    timeout 5s uvicorn api.server:app --host 127.0.0.1 --port 8000 &> /tmp/agent_test.log &
    SERVER_PID=$!
    
    # Wait for server to start
    sleep 2
    
    # Test health endpoint
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        check "API server health endpoint responds"
    else
        warn "API server health check failed (check logs: /tmp/agent_test.log)"
    fi
    
    # Kill test server
    kill $SERVER_PID 2>/dev/null || true
    wait $SERVER_PID 2>/dev/null || true
fi

# 9. Summary
echo ""
echo "========================================"
echo "📊 Summary"
echo "========================================"

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo "🎉 Your DevOps AI Agent is ready to use!"
    echo ""
    echo "Next steps:"
    echo "  1. Start the agent: uvicorn api.server:app --reload --port 8000"
    echo "  2. Test with: curl http://localhost:8000/health"
    echo "  3. See GETTING_STARTED.md for more"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ Setup complete with $WARNINGS warning(s)${NC}"
    echo ""
    echo "Your agent should work, but some features may be limited."
    echo "Review warnings above and configure as needed."
    exit 0
else
    echo -e "${RED}✗ Setup incomplete: $ERRORS error(s), $WARNINGS warning(s)${NC}"
    echo ""
    echo "Please fix the errors above before running the agent."
    echo "See GETTING_STARTED.md for help."
    exit 1
fi
