"""
Setup script for real data integration
Installs required packages and provides API key setup instructions
"""

import subprocess
import sys
import os
from pathlib import Path


def install_package(package):
    """Install a package using pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ Successfully installed {package}")
        return True
    except subprocess.CalledProcessError:
        print(f"❌ Failed to install {package}")
        return False


def check_package(package):
    """Check if a package is already installed"""
    try:
        __import__(package)
        return True
    except ImportError:
        return False


def main():
    print("🔧 Setting up Real Market Data Integration")
    print("=" * 50)
    
    # Required packages for real data feeds
    packages = [
        "aiohttp",
        "websockets", 
        "yfinance"
    ]
    
    # Check and install packages
    for package in packages:
        if check_package(package):
            print(f"✅ {package} already installed")
        else:
            print(f"📦 Installing {package}...")
            install_package(package)
    
    print("\n📋 API Key Setup Instructions")
    print("=" * 30)
    print("For enhanced real-time data, set these environment variables:")
    print()
    print("1. Alpha Vantage (Free: 5 calls/min, 500/day)")
    print("   - Get key: https://www.alphavantage.co/support/#api-key")
    print("   - Set: ALPHA_VANTAGE_API_KEY=your_key_here")
    print()
    print("2. Twelve Data (Free: 800 calls/day)")
    print("   - Get key: https://twelvedata.com/pricing")
    print("   - Set: TWELVE_DATA_API_KEY=your_key_here")
    print()
    print("💡 Without API keys, the system will use Yahoo Finance (free, rate limited)")
    print()
    
    # Create .env template
    env_file = Path(".env")
    if not env_file.exists():
        print("📝 Creating .env template file...")
        with open(env_file, "w") as f:
            f.write("# Market Data API Keys\n")
            f.write("# Alpha Vantage (free tier: 5 calls/min, 500/day)\n")
            f.write("ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key_here\n")
            f.write("\n")
            f.write("# Twelve Data (free tier: 800 calls/day)\n")
            f.write("TWELVE_DATA_API_KEY=your_twelve_data_key_here\n")
            f.write("\n")
        print("✅ Created .env template - add your API keys there")
    
    print("\n🚀 Setup Complete!")
    print("You can now run:")
    print("  python src/enhanced_paper_trading.py")
    print("  python src/data/real_data_feed.py")


if __name__ == "__main__":
    main()
