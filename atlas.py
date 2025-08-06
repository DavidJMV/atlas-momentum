#!/usr/bin/env python3
"""
Atlas Trading System Launcher
Quick launcher for various system functions
"""

import sys
import os
import argparse

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def run_setup_test():
    """Run setup validation"""
    print("Running setup validation...")
    from tests.test_setup import run_setup_validation
    return run_setup_validation()

def run_backtest():
    """Run full backtest"""
    print("Running complete backtest analysis...")
    try:
        from src.main import main
        return main()
    except ImportError as e:
        print(f"Import error: {e}")
        print("Note: Some dependencies like ta-lib may need to be installed separately")
        print("For now, the core system is configured and ready for development")
        return False

def run_monte_carlo():
    """Run Monte Carlo analysis"""
    print("Running Monte Carlo simulation...")
    try:
        from src.analysis.monte_carlo import run_complete_analysis
        return run_complete_analysis()
    except ImportError as e:
        print(f"Import error: {e}")
        print("Install required dependencies: pip install matplotlib seaborn")
        return None

def show_status():
    """Show system status"""
    print("ATLAS TRADING SYSTEM STATUS")
    print("=" * 50)
    
    # Check configuration
    try:
        from config.config import config
        print(f"✓ Configuration: Loaded")
        print(f"  - Account size: £{config.ftmo.account_size:,.0f}")
        print(f"  - Daily loss limit: £{config.ftmo.max_daily_loss:,.0f}")
        print(f"  - Trading symbol: {config.trading.symbol}")
    except Exception as e:
        print(f"✗ Configuration: Error - {e}")
    
    # Check dependencies
    missing_deps = []
    try:
        import backtrader
        print("✓ Backtrader: Available")
    except ImportError:
        missing_deps.append("backtrader")
    
    try:
        import pandas
        print("✓ Pandas: Available")
    except ImportError:
        missing_deps.append("pandas")
    
    try:
        import talib
        print("✓ TA-Lib: Available")
    except ImportError:
        print("⚠ TA-Lib: Not installed (optional for some features)")
    
    if missing_deps:
        print(f"\n⚠ Missing dependencies: {', '.join(missing_deps)}")
        print("Install with: pip install " + " ".join(missing_deps))
    
    print("\n✓ System ready for FTMO evaluation development")

def main():
    parser = argparse.ArgumentParser(description="Atlas Trading System Launcher")
    parser.add_argument("command", choices=["test", "backtest", "monte-carlo", "status"], 
                       help="Command to run")
    
    args = parser.parse_args()
    
    if args.command == "test":
        run_setup_test()
    elif args.command == "backtest":
        run_backtest()
    elif args.command == "monte-carlo":
        run_monte_carlo()
    elif args.command == "status":
        show_status()

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # No arguments provided, show status by default
        show_status()
    else:
        main()
