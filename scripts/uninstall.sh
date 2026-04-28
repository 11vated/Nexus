#!/bin/bash
# Nexus Uninstall Script

set -e

echo "Uninstalling Nexus..."
echo ""

# Stop any running instances
echo "Stopping Nexus processes..."
pkill -f "nexus" 2>/dev/null || true

# Remove virtual environment
if [ -d "$HOME/.nexus" ]; then
    echo "Removing Nexus environment..."
    rm -rf "$HOME/.nexus"
fi

# Remove config (ask first)
if [ -d "$HOME/.config/nexus" ]; then
    read -p "Remove Nexus config? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$HOME/.config/nexus"
        echo "✓ Config removed"
    fi
fi

# Remove workspace (ask first)
if [ -d "$HOME/nexus_workspace" ]; then
    read -p "Remove workspace? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$HOME/nexus_workspace"
        echo "✓ Workspace removed"
    fi
fi

# Remove cache
if [ -d "$HOME/.cache/nexus" ]; then
    rm -rf "$HOME/.cache/nexus"
    echo "✓ Cache removed"
fi

echo ""
echo "Nexus uninstalled successfully!"