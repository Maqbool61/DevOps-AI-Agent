#!/bin/bash

# DevOps AI Agent - Dependency Installation Script
# This script helps you install dependencies based on which platforms you're using

set -e

echo "=========================================="
echo "DevOps AI Agent - Dependency Installer"
echo "=========================================="
echo ""

# Core dependencies (always required)
echo "📦 Installing core dependencies..."
pip install -r requirements.txt

echo ""
echo "Select cloud providers to install (separate with spaces):"
echo "1) AWS"
echo "2) GCP"
echo "3) Azure"
echo "4) All"
echo "5) None (skip cloud providers)"
echo ""
read -p "Enter your choice (e.g., '1 3' for AWS and Azure): " cloud_choice

# Install cloud provider dependencies
if [[ "$cloud_choice" == *"4"* ]] || [[ "$cloud_choice" == *"all"* ]]; then
    echo "📦 Installing all cloud provider dependencies..."
    
    echo "  → AWS (boto3)..."
    pip install boto3 botocore
    
    echo "  → GCP (google-cloud)..."
    pip install google-cloud-compute google-cloud-container \
                google-cloud-run google-cloud-functions \
                google-cloud-logging google-cloud-sql
    
    echo "  → Azure (azure-mgmt)..."
    pip install azure-identity azure-mgmt-compute \
                azure-mgmt-containerservice azure-mgmt-web \
                azure-mgmt-sql azure-mgmt-monitor
else
    if [[ "$cloud_choice" == *"1"* ]]; then
        echo "📦 Installing AWS dependencies (boto3)..."
        pip install boto3 botocore
    fi
    
    if [[ "$cloud_choice" == *"2"* ]]; then
        echo "📦 Installing GCP dependencies (google-cloud)..."
        pip install google-cloud-compute google-cloud-container \
                    google-cloud-run google-cloud-functions \
                    google-cloud-logging google-cloud-sql
    fi
    
    if [[ "$cloud_choice" == *"3"* ]]; then
        echo "📦 Installing Azure dependencies (azure-mgmt)..."
        pip install azure-identity azure-mgmt-compute \
                    azure-mgmt-containerservice azure-mgmt-web \
                    azure-mgmt-sql azure-mgmt-monitor
    fi
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env"
echo "2. Fill in your API keys and credentials"
echo "3. Configure the platforms you want to use"
echo "4. Run: uvicorn api.server:app --reload --port 8000"
echo ""
echo "📚 See MULTI_PLATFORM_GUIDE.md for detailed configuration"
echo ""
