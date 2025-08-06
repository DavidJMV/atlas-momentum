#!/usr/bin/env python3
"""
Simple Live Data Test
Minimal test to get any historical data from IB
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import threading
import time
import pandas as pd
from datetime import datetime

class SimpleDataApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.data = []
        self.completed = False
        
    def historicalData(self, reqId, bar):
        self.data.append({
            'datetime': pd.to_datetime(bar.date),
            'open': float(bar.open),
            'high': float(bar.high),
            'low': float(bar.low),
            'close': float(bar.close),
            'volume': int(bar.volume)
        })
        
    def historicalDataEnd(self, reqId, start, end):
        self.completed = True
        print(f"✅ Historical data complete: {len(self.data)} bars")

def test_simple_nq_data():
    """Simple test to get NQ data"""
    print("🧪 SIMPLE NQ DATA TEST")
    print("=" * 40)
    
    app = SimpleDataApp()
    
    try:
        # Connect
        print("🔌 Connecting...")
        app.connect("127.0.0.1", 7497, 0)
        
        # Start message loop in thread
        thread = threading.Thread(target=app.run, daemon=True)
        thread.start()
        
        # Wait for connection
        time.sleep(2)
        
        # Create NQ contract
        contract = Contract()
        contract.symbol = "NQ"
        contract.secType = "FUT"
        contract.exchange = "CME"
        contract.currency = "USD"
        contract.lastTradeDateOrContractMonth = "20250919"  # Sept 2025 current front month
        
        print("📊 Requesting NQ data...")
        
        # Request data with correct format
        end_time = ""  # Empty for current time
        
        app.reqHistoricalData(
            1,                    # reqId
            contract,             # contract
            end_time,            # endDateTime - empty for current
            "1 D",               # durationStr (1 day)
            "1 min",             # barSizeSetting
            "TRADES",            # whatToShow
            1,                   # useRTH
            1,                   # formatDate
            False,               # keepUpToDate
            []                   # chartOptions
        )
        
        # Wait for completion
        timeout = 30
        while timeout > 0 and not app.completed:
            time.sleep(1)
            timeout -= 1
            if timeout % 5 == 0:
                print(f"   Waiting... {len(app.data)} bars received")
        
        if app.data:
            df = pd.DataFrame(app.data)
            df.set_index('datetime', inplace=True)
            df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            
            print(f"\n✅ SUCCESS! Got {len(df)} NQ bars")
            print(f"📈 Price range: ${df['Close'].min():.2f} - ${df['Close'].max():.2f}")
            print(f"📊 Latest: ${df['Close'].iloc[-1]:.2f}")
            print("\n📋 Last 5 bars:")
            print(df.tail())
            
            return df
        else:
            print("❌ No data received")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None
        
    finally:
        app.disconnect()

if __name__ == "__main__":
    test_simple_nq_data()
