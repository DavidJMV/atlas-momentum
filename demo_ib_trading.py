"""
Interactive Brokers Demo for Atlas Strategy
Quick demonstration of IB data integration
"""

import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from data.ib_integration import IBPaperTradingEngine, IBDataProvider
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False
    print("❌ IB API not available")
    print("Run: python setup_ib.py")


async def demo_ib_connection():
    """Demo IB connection and basic functionality"""
    print("🔍 Testing IB Connection")
    print("=" * 30)
    
    if not IB_AVAILABLE:
        return False
    
    try:
        # Create IB data provider
        ib_provider = IBDataProvider()
        
        print("Connecting to TWS...")
        if await ib_provider.connect():
            print("✅ Connected successfully!")
            
            # Test account info
            print("\n📊 Account Information:")
            account_info = ib_provider.get_account_info()
            if account_info:
                for key, value in account_info.items():
                    print(f"  {key}: {value}")
            else:
                print("  Requesting account updates...")
                
            # Test positions
            print("\n📈 Current Positions:")
            positions = ib_provider.get_positions()
            if positions:
                for symbol, pos_data in positions.items():
                    print(f"  {symbol}: {pos_data}")
            else:
                print("  No positions found")
                
            return True
        else:
            print("❌ Connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        return False
    finally:
        if 'ib_provider' in locals():
            ib_provider.disconnect()


async def demo_market_data():
    """Demo market data subscription"""
    print("\n📡 Testing Market Data")
    print("=" * 30)
    
    if not IB_AVAILABLE:
        return False
    
    try:
        ib_provider = IBDataProvider()
        
        if await ib_provider.connect():
            print("Connected to TWS for market data test")
            
            # Data collector
            data_received = []
            
            def collect_data(market_data):
                data_received.append(market_data)
                symbol = market_data['symbol']
                price = market_data['price']
                timestamp = market_data['timestamp']
                print(f"📊 {symbol}: ${price:.2f} at {timestamp.strftime('%H:%M:%S')}")
            
            ib_provider.subscribe(collect_data)
            
            # Try to subscribe to NQ futures
            print("\nAttempting to subscribe to NQ futures...")
            nq_success = await ib_provider.subscribe_to_market_data("NQ", "FUT")
            
            if nq_success:
                print("✅ NQ subscription successful")
            else:
                print("⚠️ NQ subscription failed - trying UK equity instead")
                # Try UK equity as fallback
                await ib_provider.subscribe_to_market_data("BARC", "STK")
            
            # Collect data for 30 seconds
            print("Collecting data for 30 seconds...")
            await asyncio.sleep(30)
            
            print(f"\n✅ Test completed! Received {len(data_received)} data points")
            return len(data_received) > 0
            
        else:
            print("❌ Connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Market data test failed: {e}")
        return False
    finally:
        if 'ib_provider' in locals():
            ib_provider.disconnect()


async def demo_paper_trading():
    """Demo paper trading with IB"""
    print("\n🎯 Paper Trading Demo")
    print("=" * 30)
    
    if not IB_AVAILABLE:
        return False
    
    try:
        # Create paper trading engine
        engine = IBPaperTradingEngine("paper")
        
        print("Starting paper trading demo for 60 seconds...")
        print("This will attempt to connect to TWS and stream market data")
        
        # Start paper trading (will run until interrupted)
        trading_task = asyncio.create_task(engine.start_paper_trading(["NQ"]))
        
        # Let it run for 60 seconds
        await asyncio.sleep(60)
        
        # Cancel the task
        trading_task.cancel()
        
        print("✅ Paper trading demo completed")
        return True
        
    except Exception as e:
        print(f"❌ Paper trading demo failed: {e}")
        return False


def show_setup_instructions():
    """Show setup instructions"""
    print("\n📋 Setup Instructions")
    print("=" * 25)
    print("1. Install IB API:")
    print("   python setup_ib.py")
    print()
    print("2. Start TWS or IB Gateway:")
    print("   - Paper Trading: Use demo/paper account")
    print("   - Enable API connections in settings")
    print("   - Configure port 7497 for paper trading")
    print()
    print("3. Configure TWS:")
    print("   - File > Global Configuration > API > Settings")
    print("   - Enable 'ActiveX and Socket Clients'")
    print("   - Set Socket port to 7497")
    print("   - Add 127.0.0.1 to trusted IPs if needed")
    print()
    print("4. Check market data subscriptions:")
    print("   - Account Management > Market Data Subscriptions")
    print("   - Verify UK equities access")
    print("   - Consider adding CME futures for NQ")


async def main():
    """Main demo function"""
    print("🎯 Interactive Brokers Demo for Atlas Strategy")
    print("=" * 50)
    
    if not IB_AVAILABLE:
        show_setup_instructions()
        return
    
    # Menu
    print("Select demo:")
    print("1. Test IB connection")
    print("2. Test market data feed")
    print("3. Test paper trading")
    print("4. Run all tests")
    print("5. Show setup instructions")
    
    choice = input("\nEnter choice (1-5): ").strip()
    
    try:
        if choice == "1":
            await demo_ib_connection()
        elif choice == "2":
            await demo_market_data()
        elif choice == "3":
            await demo_paper_trading()
        elif choice == "4":
            print("Running all tests...")
            await demo_ib_connection()
            await demo_market_data()
            await demo_paper_trading()
        elif choice == "5":
            show_setup_instructions()
        else:
            print("Invalid choice")
            
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"Demo error: {e}")


if __name__ == "__main__":
    print("Interactive Brokers Integration Demo")
    print()
    
    if not IB_AVAILABLE:
        print("⚠️ Setup required first")
        show_setup_instructions()
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("\nDemo terminated by user")
        except Exception as e:
            print(f"Demo failed: {e}")
