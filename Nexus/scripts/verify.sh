#!/bin/bash
# Verification script for Nexus production readiness

set -e

echo "=== Nexus Final Verification ==="

# 1. Check imports
echo "Checking imports..."
python -c "from src.nexus.swe_bench import SWEBenchOrchestrator; from src.nexus.gateway.client import GatewayClient; from src.nexus.core.cache import ResponseCache; print('✅ All modules import')"

# 2. Check tests pass
echo "Running tests..."
pytest tests/ -v -x --tb=short || { echo "❌ Tests failed"; exit 1; }

# 3. Check for security issues (shell=True)
echo "Checking for shell=True..."
if grep -r "shell=True" src/ 2>/dev/null; then
    echo "❌ Found shell=True - security risk"
    exit 1
else
    echo "✅ No dangerous shell=True calls"
fi

# 4. Check for hardcoded paths
echo "Checking for hardcoded paths..."
if grep -r "C:/Users" src/ 2>/dev/null; then
    echo "❌ Found hardcoded Windows paths"
    exit 1
else
    echo "✅ No hardcoded paths"
fi

# 5. Check gateway config
echo "Checking gateway config..."
if [ -f gateway_config.yaml ]; then
    echo "✅ gateway_config.yaml exists"
else
    echo "❌ gateway_config.yaml missing"
    exit 1
fi

echo "=== All checks passed. Nexus is production ready. ==="