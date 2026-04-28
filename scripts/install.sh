#!/bin/bash
# Nexus Installation Script
# Supports Linux, macOS, and Windows (via WSL)

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           Nexus AI Workstation Installation                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        echo "windows"
    else
        echo "unknown"
    fi
}

# Check Python version
check_python() {
    if ! command -v python3 &> /dev/null; then
        echo "Error: Python 3 is required but not installed."
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    REQUIRED_VERSION="3.10"
    
    if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
        echo "Error: Python $REQUIRED_VERSION+ required, found $PYTHON_VERSION"
        exit 1
    fi
    
    echo "✓ Python $PYTHON_VERSION detected"
}

# Check Ollama
check_ollama() {
    if command -v ollama &> /dev/null; then
        echo "✓ Ollama found"
        OLLAMA_VERSION=$(ollama --version 2>/dev/null || echo "unknown")
        echo "  Version: $OLLAMA_VERSION"
    else
        echo "⚠ Ollama not found - will be required for AI features"
        echo "  Install: curl -fsSL https://ollama.com/install.sh | sh"
    fi
}

# Install function
install_nexus() {
    echo ""
    echo "Installing Nexus..."
    
    # Create virtual environment
    echo "Creating virtual environment..."
    python3 -m venv "$HOME/.nexus/venv"
    
    # Activate and install
    source "$HOME/.nexus/venv/bin/activate"
    
    echo "Installing dependencies..."
    pip install --upgrade pip
    pip install -e ".[all]"
    
    # Create config directory
    mkdir -p "$HOME/.config/nexus"
    
    # Copy env example if not exists
    if [ ! -f "$HOME/.config/nexus/.env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example "$HOME/.config/nexus/.env"
            echo "✓ Created config at $HOME/.config/nexus/.env"
        fi
    fi
    
    # Create workspace
    mkdir -p "$HOME/nexus_workspace"
    
    echo ""
    echo "✓ Installation complete!"
    echo ""
    echo "To activate Nexus:"
    echo "  source $HOME/.nexus/venv/bin/activate"
    echo ""
    echo "To start the CLI:"
    echo "  nexus --help"
    echo ""
    echo "To enable Ollama (if installed):"
    echo "  ollama pull qwen2.5-coder:14b"
}

# Main
main() {
    OS=$(detect_os)
    echo "Detected OS: $OS"
    echo ""
    
    check_python
    check_ollama
    
    install_nexus
}

main "$@"