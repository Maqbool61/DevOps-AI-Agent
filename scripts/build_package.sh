#!/usr/bin/env bash
# Build Python wheel and sdist for devops-ai-agent
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Building devops-ai-agent Python package..."
python3 -m pip install --upgrade build wheel setuptools >/dev/null
python3 -m build

echo ""
echo "Done. Artifacts:"
ls -la dist/
echo ""
echo "Install locally:"
echo "  pip install dist/devops_ai_agent-*.whl"
echo ""
echo "Install with cloud extras:"
echo "  pip install 'dist/devops_ai_agent-*.whl[aws,gcp,azure]'"
echo ""
echo "Publish to PyPI (after configuring credentials):"
echo "  python3 -m pip install twine"
echo "  twine upload dist/*"
