#!/usr/bin/env python3
"""
Live CME Data Monitor
Shows real-time NQ data from professional CME feed
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

class LiveMonitor(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.data = []
        self.completed = False
        
    def historicalData(self, reqId, bar):
        price = float(bar.close)
        vol = int(bar.volume)
        timestamp = pd.to_datetime(bar.date)
        
        print(f"📊 {timestamp.strftime('%H:%M:%S')} | NQ: ${price:,.2f} | Vol: {vol:,}")
        
        self.data.append({
            'time': timestamp,
            'price': price,
            'volume': vol,
            'open': float(bar.open),
            'high': float(bar.high),
            'low': float(bar.low)
        })
        
    def historicalDataEnd(self, reqId, start, end):
        self.completed = True
        print(f"\n✅ COMPLETE: {len(self.data)} bars collected")
        
        if self.data:
            df = pd.DataFrame(self.data)
            latest = df.iloc[-1]
            first = df.iloc[0]
            
            price_change = latest['price'] - first['price']
            price_change_pct = (price_change / first['price']) * 100
            
            print(f"\n📈 SESSION SUMMARY:")
            print(f"   Period: {first['time'].strftime('%H:%M')} - {latest['time'].strftime('%H:%M')}")
            print(f"   Open: ${first['open']:,.2f}")
            print(f"   Current: ${latest['price']:,.2f}")
            print(f"   High: ${df['high'].max():,.2f}")
            print(f"   Low: ${df['low'].min():,.2f}")
            print(f"   Change: ${price_change:+,.2f} ({price_change_pct:+.2f}%)")
            print(f"   Total Volume: {df['volume'].sum():,}")
            print(f"   Avg Volume/bar: {df['volume'].mean():,.0f}")
            
            # Calculate some basic stats for strategy assessment
            volatility = df['price'].std()
            price_range = df['high'].max() - df['low'].min()
            
            print(f"\n📊 TRADING CONDITIONS:")
            print(f"   Volatility (std): ${volatility:.2f}")
            print(f"   Session Range: ${price_range:.2f}")
            print(f"   Tick Movement: ${price_change:.2f} points")
            
            if price_range > 50:
                print(f"   ✅ Good volatility for scalping")
            else:
                print(f"   ⚠️  Low volatility session")
                
            if df['volume'].mean() > 1000:
                print(f"   ✅ Good liquidity")
            else:
                print(f"   ⚠️  Lower liquidity")

def monitor_live_nq():
    """Monitor live NQ data feed"""
    print("🔴 LIVE NQ DATA MONITOR")
    print("Source: CME Real-Time Professional Feed")
    print("=" * 50)
    
    app = LiveMonitor()
    
    try:
        print("🔌 Connecting to TWS...")
        app.connect("127.0.0.1", 7497, 0)
        
        thread = threading.Thread(target=app.run, daemon=True)
        thread.start()
        time.sleep(2)
        
        # NQ contract (September 2025)
        contract = Contract()
        contract.symbol = "NQ"
        contract.secType = "FUT"
        contract.exchange = "CME"
        contract.currency = "USD"
        contract.lastTradeDateOrContractMonth = "20250919"
        
        print("📊 Requesting live session data...")
        print("Data updates will appear below:\n")
        
        # Get today's session data
        app.reqHistoricalData(
            1, contract, "", "1 D", "1 min", "TRADES", 1, 1, False, []
        )
        
        # Wait for completion
        timeout = 45
        while timeout > 0 and not app.completed:
            time.sleep(1)
            timeout -= 1
        
        if not app.data:
            print("❌ No live data received")
            print("   Market may be closed or connection issue")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        app.disconnect()

if __name__ == "__main__":
    print("🎯 Purpose: Monitor real-time CME data quality")
    print("💰 Data Cost: $1.25/month CME Real-Time subscription")
    print("🏦 Data Quality: Professional institutional-grade")
    print()
    
    try:
        monitor_live_nq()
        
        print(f"\n💡 NEXT STEPS:")
        print(f"   1. Monitor data quality and market conditions")
        print(f"   2. Collect sufficient data for strategy backtesting")
        print(f"   3. Run optimized Atlas strategy when enough bars accumulated")
        print(f"   4. Validate FTMO performance with real professional data")
        
    except KeyboardInterrupt:
        print("\n⚠️  Monitoring stopped by user")
    except Exception as e:
        print(f"\n❌ Monitor failed: {e}")
