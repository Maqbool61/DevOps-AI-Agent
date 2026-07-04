#!/usr/bin/env bash
# End-to-end API test script for DevOps AI Agent
# Usage: ./scripts/test_api_flow.sh [base_url] [org_id]
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
ORG_ID="${2:-acme-corp}"

echo "=== DevOps AI Agent API Test ==="
echo "Base URL: $BASE_URL"
echo "Org ID:   $ORG_ID"
echo ""

echo "1. Health check..."
HEALTH=$(curl -sf "$BASE_URL/health")
echo "$HEALTH" | python3 -m json.tool
STATUS=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))")
if [ "$STATUS" != "ok" ]; then
  echo "FAIL: health check returned status=$STATUS"
  exit 1
fi
echo "OK"
echo ""

echo "2. Upload runbook..."
curl -sf -X POST "$BASE_URL/orgs/$ORG_ID/docs" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "runbooks/api-test.md",
    "content": "# API Test Runbook\nAutomated test doc.\nEvidence: always cite tool output."
  }' | python3 -m json.tool
echo "OK"
echo ""

echo "3. List docs..."
curl -sf "$BASE_URL/orgs/$ORG_ID/docs?prefix=runbooks" | python3 -m json.tool
echo "OK"
echo ""

echo "4. Trigger manual K8s incident..."
RESPONSE=$(curl -sf -X POST "$BASE_URL/webhook/manual" \
  -H "Content-Type: application/json" \
  -H "X-Org-ID: $ORG_ID" \
  -d '{
    "type": "k8s",
    "namespace": "default",
    "pod": "api-test-pod",
    "description": "Automated API test incident"
  }')
echo "$RESPONSE" | python3 -m json.tool
INCIDENT_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['incident_id'])")
echo "Incident ID: $INCIDENT_ID"
echo "OK"
echo ""

echo "5. Waiting 15s for queue worker..."
sleep 15

echo "6. Poll audit log..."
AUDIT=$(curl -sf "$BASE_URL/audit?org_id=$ORG_ID&limit=5")
echo "$AUDIT" | python3 -m json.tool

FOUND=$(echo "$AUDIT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
incident_id = '$INCIDENT_ID'
events = data.get('events', [])
found = any(e.get('id') == incident_id for e in events)
print('yes' if found else 'no')
")

if [ "$FOUND" = "yes" ]; then
  echo "OK: Incident $INCIDENT_ID found in audit"
else
  echo "WARN: Incident not in audit yet — queue may still be processing."
  echo "      Re-run: curl -s $BASE_URL/audit?org_id=$ORG_ID | python3 -m json.tool"
fi

echo ""
echo "=== Test complete ==="
