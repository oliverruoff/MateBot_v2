#!/bin/bash
# Quick setup and test script for Raspberry Pi
# Run this on your Raspberry Pi to install and test motors

set -e  # Exit on error

echo "=========================================="
echo "MateBot v2 - Quick Motor Test Setup"
echo "=========================================="
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "Detected Python version: $PYTHON_VERSION"
echo ""

# Navigate to project
cd ~/develop/MateBot_v2

# Pull latest code
echo "Pulling latest code from GitHub..."
git pull
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo ""

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel
echo ""

# Install minimal requirements for motor testing
echo "Installing minimal requirements for motor testing..."
echo "(This skips heavy packages like numpy, opencv, scipy)"
pip install -r requirements-minimal.txt
echo ""

# Check if pigpiod is running
echo "Checking pigpio daemon..."
if pigs hwver &> /dev/null; then
    echo "✓ pigpiod is running"
else
    echo "⚠ pigpiod is not running. Starting it now..."
    sudo pigpiod
    sleep 2
    if pigs hwver &> /dev/null; then
        echo "✓ pigpiod started successfully"
    else
        echo "✗ Failed to start pigpiod. Run manually: sudo pigpiod"
        exit 1
    fi
fi
echo ""

echo "=========================================="
echo "✓ Setup Complete!"
echo "=========================================="
echo ""
echo "Ready to test motors!"
echo ""
echo "Run the test with:"
echo "  python test_motors.py"
echo ""
echo "Controls:"
echo "  W - Forward"
echo "  S - Backward"
echo "  A - Strafe Left"
echo "  D - Strafe Right"
echo "  Q - Rotate Left"
echo "  E - Rotate Right"
echo "  X - Stop"
echo "  ESC - Exit"
echo ""
echo "Happy testing! 🤖"
