#!/usr/bin/env python3
"""
Test IB Historical Data Collection
Verifies that the fixed IB integration can collect historical data
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

import asyncio
import time
from datetime import datetime, timedelta
from src.data.ib_integration import IBDataProvider

async def test_ib_historical_data():
    """Test IB historical data collection"""
    print("🧪 TESTING IB HISTORICAL DATA COLLECTION")
    print("=" * 50)
    
    # Initialize IB provider
    provider = IBDataProvider()
    
    try:
        print("🔌 Connecting to TWS...")
        connected = provider.connect()  # Use sync method
        
        if not connected:
            print("❌ Failed to connect to TWS")
            print("💡 Make sure TWS is running on port 7497")
            return False
        
        print("✅ Connected to TWS")
        
        # Test historical data collection
        print("📊 Requesting historical data...")
        
        # Try to get recent NQ data (if CME subscription active)
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=2)
        
        # Test with NQ futures
        print("🔍 Testing NQ futures data...")
        nq_data = provider.get_historical_data(
            symbol="NQ",
            exchange="CME",
            start_time=start_time,
            end_time=end_time,
            bar_size="1 min"
        )
        
        if nq_data is not None and len(nq_data) > 0:
            print(f"✅ NQ Data Retrieved: {len(nq_data)} bars")
            print(f"📈 Price range: ${nq_data['Close'].min():.2f} - ${nq_data['Close'].max():.2f}")
            print(f"📊 Sample data:")
            print(nq_data.head())
            return True
        else:
            print("⚠️ No NQ data received (may need market hours or subscription)")
            
            # Try UK equity data (should be available)
            print("🔍 Testing UK equity data...")
            equity_data = provider.get_historical_data(
                symbol="BARC",  # Barclays
                exchange="LSE",
                start_time=start_time,
                end_time=end_time,
                bar_size="1 min"
            )
            
            if equity_data is not None and len(equity_data) > 0:
                print(f"✅ UK Equity Data Retrieved: {len(equity_data)} bars")
                print(f"📈 Price range: £{equity_data['Close'].min():.2f} - £{equity_data['Close'].max():.2f}")
                return True
            else:
                print("❌ No historical data received")
                return False
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
        
    finally:
        provider.disconnect()
        print("🔌 Disconnected from TWS")

def test_ib_data_sync():
    """Synchronous wrapper for the test"""
    return asyncio.run(test_ib_historical_data())

if __name__ == "__main__":
    success = test_ib_data_sync()
    
    if success:
        print("\n✅ IB HISTORICAL DATA COLLECTION: WORKING")
        print("🎯 Ready for live optimization")
    else:
        print("\n❌ IB HISTORICAL DATA COLLECTION: FAILED")
        print("💡 Check TWS connection and market data subscriptions")
