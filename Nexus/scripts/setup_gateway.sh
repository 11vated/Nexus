#!/bin/bash
# LiteLLM Gateway Setup for Nexus
# This script sets up the unified model gateway

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║         Nexus Unified Model Gateway Setup                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 required but not found"
    exit 1
fi

echo "✓ Python detected"
echo ""

# Install LiteLLM
echo "Installing LiteLLM..."
pip install 'litellm[proxy]' --quiet

echo "✓ LiteLLM installed"
echo ""

# Check for .env file
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cat > .env << 'EOF'
# LiteLLM Settings
LITELLM_MASTER_KEY=your-secret-key-here
OPENAI_API_KEY=sk-your-openai-key  # Optional
ANTHROPIC_API_KEY=sk-ant-your-key   # Optional
EOF
    echo "✓ Created .env (edit with your API keys)"
fi

# Create logs directory
mkdir -p logs

echo ""
echo "✓ Configuration complete!"
echo ""
echo "To start the gateway:"
echo "  litellm --config gateway_config.yaml --port 4000"
echo ""
echo "Gateway will be available at: http://localhost:4000"
echo ""
echo "To configure your tools to use the gateway:"
echo ""
echo "=== OpenCode (opencode.json) ==="
echo '{"providers": {"nexus": {"type": "openai", "apiBase": "http://localhost:4000/v1"}}}'
echo ""
echo "=== Aider ==="
echo "aider --model gpt-4o --openai-api-base http://localhost:4000/v1 --api-key dummy"
echo ""
echo "=== Goose (config.yaml) ==="
echo "llm:"
echo "  provider: openai"
echo "  api_base: http://localhost:4000/v1"
echo ""
echo "=== Direct Python ==="
echo "import requests"
echo 'response = requests.post(\"http://localhost:4000/v1/chat/completions\",'
echo '  headers={\"Authorization\": \"Bearer dummy\"},'
echo '  json={\"model\": \"qwen2.5-coder:14b\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello\"}]}'
echo ')'