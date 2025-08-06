"""
Demo Script - Enhanced Paper Trading with Real Data
Quick demonstration of the paper trading system
"""

import sys
import asyncio
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from enhanced_paper_trading import EnhancedPaperTradingEngine, quick_test
    SYSTEM_READY = True
except ImportError as e:
    print(f"❌ System not ready: {e}")
    print("Please run: python setup_real_data.py")
    SYSTEM_READY = False


async def demo_quick_test():
    """Quick 5-minute demo"""
    print("🎯 5-Minute Paper Trading Demo")
    print("=" * 35)
    print("This will simulate paper trading for 5 minutes")
    print("Press Ctrl+C to stop early")
    print()
    
    await quick_test(duration_minutes=5, real_data=True)


async def demo_custom_session():
    """Customizable demo session"""
    print("🎯 Custom Paper Trading Session")
    print("=" * 35)
    
    # Get user preferences
    try:
        balance = float(input("Initial balance (50000): ") or "50000")
        duration = int(input("Duration in minutes (30): ") or "30")
        use_real_data = input("Use real market data? (y/N): ").lower().startswith('y')
    except ValueError:
        print("Using defaults...")
        balance = 50000.0
        duration = 30
        use_real_data = False
    
    print(f"\nStarting paper trading:")
    print(f"  Balance: ${balance:,.2f}")
    print(f"  Duration: {duration} minutes")
    print(f"  Data: {'Real market data' if use_real_data else 'Simulated'}")
    print("  Press Ctrl+C to stop early")
    print()
    
    # Create and run engine
    engine = EnhancedPaperTradingEngine(
        initial_balance=balance,
        enable_real_data=use_real_data
    )
    
    await engine.start_paper_trading("NQ", duration_minutes=duration)


def show_menu():
    """Show demo menu"""
    print("🚀 Atlas Strategy - Paper Trading Demo")
    print("=" * 40)
    print("1. Quick 5-minute demo")
    print("2. Custom session")
    print("3. Real data feed test")
    print("4. Exit")
    print()
    
    choice = input("Select option (1-4): ").strip()
    return choice


async def test_real_data():
    """Test real data feed"""
    print("🔍 Testing Real Market Data Feed")
    print("=" * 35)
    
    try:
        from data.real_data_feed import DataFeedManager
        
        feed = DataFeedManager()
        data_count = 0
        
        async def show_data(market_data):
            nonlocal data_count
            data_count += 1
            print(f"📊 {market_data.symbol}: ${market_data.close:.2f} "
                  f"(Bid: {market_data.bid:.2f}, Ask: {market_data.ask:.2f})")
        
        feed.subscribe(show_data)
        
        print("Collecting data for 30 seconds...")
        print("Press Ctrl+C to stop early")
        
        # Test for 30 seconds
        feed_task = asyncio.create_task(feed.start_feed("NQ", update_interval=3))
        await asyncio.sleep(30)
        feed.stop_feed()
        
        print(f"\n✅ Test completed! Received {data_count} data points")
        
    except ImportError:
        print("❌ Real data feed not available")
        print("Run: python setup_real_data.py")
    except Exception as e:
        print(f"❌ Test failed: {e}")


async def main():
    """Main demo function"""
    if not SYSTEM_READY:
        return
    
    while True:
        choice = show_menu()
        
        try:
            if choice == "1":
                await demo_quick_test()
            elif choice == "2":
                await demo_custom_session()
            elif choice == "3":
                await test_real_data()
            elif choice == "4":
                print("Thanks for trying the demo!")
                break
            else:
                print("Invalid choice. Please try again.")
                continue
                
        except KeyboardInterrupt:
            print("\nDemo interrupted by user")
        except Exception as e:
            print(f"Demo error: {e}")
        
        print("\n" + "="*40)
        input("Press Enter to continue...")


if __name__ == "__main__":
    print("Atlas Strategy Paper Trading Demo")
    print()
    
    if not SYSTEM_READY:
        print("💡 Setup required:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Setup real data: python setup_real_data.py")
        print("3. Run tests: python test_paper_trading.py")
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("\nDemo terminated by user")
        except Exception as e:
            print(f"Demo failed: {e}")
