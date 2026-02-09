#!/bin/bash

# Check if Python 3.8+ is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3.8 or higher is required. Please install it first."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
if [[ "$(printf '%s\n' "3.8" "$PYTHON_VERSION" | sort -V | head -n1)" != "3.8" ]]; then
    echo "Python 3.8 or higher is required. Found Python $PYTHON_VERSION"
    exit 1
fi

# Create and activate virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Set up environment variables
echo "Setting up environment variables..."
if [ ! -f .env ]; then
    cp .env.template .env
    echo "\nPlease edit the .env file with your Discord bot tokens and other settings."
    echo "Then run the bot with: python run_bots.py"
else
    echo "\.env file already exists. Skipping creation."
fi

echo "\nSetup complete!"
echo "1. Edit the .env file with your Discord bot tokens and other settings"
echo "2. Run the bot with: python run_bots.py"

# Make setup script executable
chmod +x setup.sh
