"""
Interactive Brokers Setup Script
Quick setup and testing for IB integration with Atlas Strategy
"""

import subprocess
import sys
import os
from pathlib import Path


def install_ib_api():
    """Install Interactive Brokers API"""
    try:
        print("📦 Installing Interactive Brokers API...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "ibapi"])
        print("✅ IB API installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install IB API")
        return False


def test_ib_import():
    """Test if IB API can be imported"""
    try:
        from ibapi.client import EClient
        from ibapi.wrapper import EWrapper
        print("✅ IB API import successful")
        return True
    except ImportError:
        print("❌ IB API import failed")
        return False


def check_tws_connection():
    """Check if TWS is running and accessible"""
    import socket
    
    # Test paper trading port (7497)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', 7497))
        sock.close()
        
        if result == 0:
            print("✅ TWS Paper Trading detected (port 7497)")
            return True, "paper"
    except:
        pass
    
    # Test live trading port (7496)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', 7496))
        sock.close()
        
        if result == 0:
            print("✅ TWS Live Trading detected (port 7496)")
            return True, "live"
    except:
        pass
    
    print("❌ TWS not detected")
    print("Please start TWS or IB Gateway first")
    return False, None


def create_ib_config():
    """Create IB configuration file"""
    config_content = """# Interactive Brokers Configuration
IB_HOST=127.0.0.1
IB_PAPER_PORT=7497
IB_LIVE_PORT=7496
IB_CLIENT_ID=1

# For NQ Futures
NQ_SYMBOL=NQ
NQ_EXCHANGE=CME
NQ_CURRENCY=USD
NQ_CONTRACT_MONTH=202508  # Adjust to current quarter

# UK Equities Examples
UK_SYMBOLS=BARC,LLOY,VOD,BT.A,TSCO
UK_EXCHANGE=LSE
UK_CURRENCY=GBP
"""
    
    config_file = Path(".env.ib")
    with open(config_file, "w") as f:
        f.write(config_content)
    
    print(f"✅ Created IB config: {config_file}")


def show_next_steps():
    """Show next steps for IB setup"""
    print("\n🚀 Next Steps:")
    print("=" * 30)
    print("1. Start TWS or IB Gateway")
    print("   - Paper Trading: Connect to port 7497")
    print("   - Enable API connections in TWS settings")
    print()
    print("2. Test the connection:")
    print("   python src/data/ib_integration.py")
    print()
    print("3. Check NQ futures data access:")
    print("   - Go to TWS Market Data subscriptions")
    print("   - Verify CME futures data is available")
    print("   - May require $1-5/month subscription")
    print()
    print("4. Run IB paper trading test:")
    print("   python demo_ib_trading.py")


def main():
    print("🔧 Interactive Brokers Setup for Atlas Strategy")
    print("=" * 50)
    
    # Check if IB API is installed
    if not test_ib_import():
        print("Installing IB API...")
        if not install_ib_api():
            print("Please install manually: pip install ibapi")
            return
    
    # Test import again
    if not test_ib_import():
        print("Installation may have failed. Please try manually.")
        return
    
    print("\n🔍 Checking TWS Connection...")
    tws_running, mode = check_tws_connection()
    
    if tws_running:
        print(f"Mode: {mode.upper()}")
    
    print("\n📝 Creating configuration files...")
    create_ib_config()
    
    print("\n📋 TWS Setup Instructions:")
    print("-" * 30)
    print("1. Open TWS or IB Gateway")
    print("2. Go to File > Global Configuration > API > Settings")
    print("3. Enable 'Enable ActiveX and Socket Clients'")
    print("4. Set 'Socket port' to 7497 (paper) or 7496 (live)")
    print("5. Add '127.0.0.1' to 'Trusted IPs' if needed")
    print("6. Click 'Apply' and restart TWS")
    
    show_next_steps()
    
    print(f"\n📊 Data Subscription Notes:")
    print("-" * 30)
    print("• UK LSE Equities: Should be included with your account")
    print("• NQ Futures: May require CME data subscription")
    print("• Cost: Typically $1-5/month for real-time futures data")
    print("• Check: Account Management > Market Data Subscriptions")
    
    print("\n✅ IB Setup Complete!")


if __name__ == "__main__":
    main()
