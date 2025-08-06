#!/usr/bin/env python3
"""
Continuous Live Data Monitor
Tracks real-time CME data accumulation for strategy readiness
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
from datetime import datetime, timedelta
import os

class ContinuousMonitor(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.data = []
        self.completed = False
        self.last_update = None
        
    def historicalData(self, reqId, bar):
        price = float(bar.close)
        vol = int(bar.volume)
        timestamp = pd.to_datetime(bar.date)
        
        self.data.append({
            'time': timestamp,
            'price': price,
            'volume': vol,
            'open': float(bar.open),
            'high': float(bar.high),
            'low': float(bar.low)
        })
        
        self.last_update = datetime.now()
        
    def historicalDataEnd(self, reqId, start, end):
        self.completed = True

def monitor_continuous_data():
    """Continuously monitor NQ data accumulation"""
    print("🔄 CONTINUOUS NQ DATA MONITOR")
    print("Tracking data accumulation for strategy readiness")
    print("=" * 60)
    
    check_interval = 60  # Check every minute
    strategy_threshold = 100  # Need 100+ bars for strategy
    
    while True:
        try:
            app = ContinuousMonitor()
            
            # Connect to IB
            app.connect("127.0.0.1", 7497, 0)
            thread = threading.Thread(target=app.run, daemon=True)
            thread.start()
            time.sleep(2)
            
            # NQ contract
            contract = Contract()
            contract.symbol = "NQ"
            contract.secType = "FUT"
            contract.exchange = "CME"
            contract.currency = "USD"
            contract.lastTradeDateOrContractMonth = "20250919"
            
            # Request current session data
            app.reqHistoricalData(
                1, contract, "", "1 D", "1 min", "TRADES", 1, 1, False, []
            )
            
            # Wait for data
            timeout = 30
            while timeout > 0 and not app.completed:
                time.sleep(1)
                timeout -= 1
            
            app.disconnect()
            
            if app.data:
                df = pd.DataFrame(app.data)
                current_time = datetime.now()
                latest_bar = df.iloc[-1]
                first_bar = df.iloc[0]
                
                # Calculate metrics
                session_duration = latest_bar['time'] - first_bar['time']
                price_change = latest_bar['price'] - first_bar['price']
                price_change_pct = (price_change / first_bar['price']) * 100
                volatility = df['price'].std()
                avg_volume = df['volume'].mean()
                
                # Clear screen and show status
                os.system('cls' if os.name == 'nt' else 'clear')
                
                print("🔴 LIVE NQ DATA ACCUMULATION MONITOR")
                print("=" * 60)
                print(f"⏰ Current Time: {current_time.strftime('%H:%M:%S GMT')}")
                print(f"📊 Session Duration: {session_duration}")
                print(f"📈 Data Bars Collected: {len(df)}")
                
                # Strategy readiness indicator
                if len(df) >= strategy_threshold:
                    print(f"✅ STRATEGY READY: {len(df)} bars (>{strategy_threshold} needed)")
                    print("🚀 Ready to run Atlas Strategy backtest!")
                else:
                    bars_needed = strategy_threshold - len(df)
                    print(f"⏳ ACCUMULATING: {len(df)} bars ({bars_needed} more needed)")
                    
                    # Estimate time to readiness
                    if len(df) > 1:
                        bars_per_minute = len(df) / (session_duration.total_seconds() / 60)
                        minutes_to_ready = bars_needed / bars_per_minute if bars_per_minute > 0 else 0
                        print(f"🕐 Est. time to ready: {minutes_to_ready:.0f} minutes")
                
                print(f"\n💰 CURRENT MARKET CONDITIONS:")
                print(f"   NQ Price: ${latest_bar['price']:,.2f}")
                print(f"   Session Change: ${price_change:+.2f} ({price_change_pct:+.2f}%)")
                print(f"   Volatility: ${volatility:.2f}")
                print(f"   Avg Volume: {avg_volume:,.0f}/min")
                print(f"   High: ${df['high'].max():,.2f}")
                print(f"   Low: ${df['low'].min():,.2f}")
                print(f"   Range: ${df['high'].max() - df['low'].min():.2f}")
                
                # Trading condition assessment
                print(f"\n📊 TRADING CONDITIONS:")
                if volatility > 15:
                    print(f"   ✅ Volatility: GOOD (${volatility:.2f})")
                else:
                    print(f"   ⚠️  Volatility: LOW (${volatility:.2f})")
                    
                if avg_volume > 2000:
                    print(f"   ✅ Liquidity: GOOD ({avg_volume:,.0f}/min)")
                else:
                    print(f"   ⚠️  Liquidity: LOW ({avg_volume:,.0f}/min)")
                    
                if abs(price_change_pct) > 0.1:
                    print(f"   ✅ Momentum: ACTIVE ({price_change_pct:+.2f}%)")
                else:
                    print(f"   ⚠️  Momentum: QUIET ({price_change_pct:+.2f}%)")
                
                # Show progress bar
                progress = min(100, (len(df) / strategy_threshold) * 100)
                bar_length = 40
                filled_length = int(bar_length * progress / 100)
                bar = '█' * filled_length + '░' * (bar_length - filled_length)
                print(f"\n📊 Data Collection Progress:")
                print(f"   [{bar}] {progress:.1f}%")
                
                print(f"\n🔄 Next update in {check_interval} seconds...")
                print("   Press Ctrl+C to stop monitoring")
                
                # If ready for strategy, give option to run
                if len(df) >= strategy_threshold:
                    print(f"\n🎯 READY TO RUN STRATEGY!")
                    print(f"   Run: python realtime_strategy_test.py")
                    break
                    
            else:
                print(f"❌ No data received at {datetime.now().strftime('%H:%M:%S')}")
                
            # Wait before next check
            time.sleep(check_interval)
            
        except KeyboardInterrupt:
            print(f"\n⚠️  Monitoring stopped by user at {datetime.now().strftime('%H:%M:%S')}")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(30)  # Wait longer on error

if __name__ == "__main__":
    print("🎯 Purpose: Monitor data accumulation for strategy readiness")
    print("📊 Target: 100+ bars needed for reliable strategy testing")
    print("⏱️  Update Interval: Every 60 seconds")
    print("🛑 Stop: Press Ctrl+C to exit")
    print()
    
    monitor_continuous_data()
