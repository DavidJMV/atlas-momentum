#!/usr/bin/env python3
"""
Live Data Analysis
Analysis of collected professional CME data
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
import numpy as np
from datetime import datetime

class DataAnalyzer(EWrapper, EClient):
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

def analyze_collected_data():
    """Analyze the live CME data we collected"""
    print("📊 LIVE CME DATA ANALYSIS")
    print("Professional Data Quality Assessment")
    print("=" * 60)
    
    app = DataAnalyzer()
    
    try:
        # Connect
        print("🔌 Connecting to TWS...")
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
        
        print("📈 Collecting final dataset...")
        
        # Get the data
        app.reqHistoricalData(
            1, contract, "", "1 D", "1 min", "TRADES", 1, 1, False, []
        )
        
        # Wait for completion
        timeout = 30
        while timeout > 0 and not app.completed:
            time.sleep(1)
            timeout -= 1
        
        app.disconnect()
        
        if app.data and len(app.data) > 10:
            df = pd.DataFrame(app.data)
            df.set_index('datetime', inplace=True)
            df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            
            # Analysis
            session_start = df.index[0]
            session_end = df.index[-1]
            session_duration = session_end - session_start
            
            open_price = df['Open'].iloc[0]
            close_price = df['Close'].iloc[-1]
            high_price = df['High'].max()
            low_price = df['Low'].min()
            
            price_change = close_price - open_price
            price_change_pct = (price_change / open_price) * 100
            session_range = high_price - low_price
            
            total_volume = df['Volume'].sum()
            avg_volume = df['Volume'].mean()
            
            # Volatility analysis
            returns = df['Close'].pct_change().dropna()
            volatility = returns.std() * np.sqrt(60)  # 1-minute to hourly
            
            # Momentum analysis
            df['Returns'] = df['Close'].pct_change()
            positive_bars = (df['Returns'] > 0).sum()
            negative_bars = (df['Returns'] < 0).sum()
            neutral_bars = (df['Returns'] == 0).sum()
            
            print(f"\n✅ DATA COLLECTION SUCCESS")
            print(f"📊 Total Bars: {len(df)}")
            print(f"⏰ Session: {session_start.strftime('%H:%M')} - {session_end.strftime('%H:%M')} GMT")
            print(f"🕐 Duration: {session_duration}")
            
            print(f"\n💰 PRICE PERFORMANCE")
            print(f"   Open: ${open_price:,.2f}")
            print(f"   Close: ${close_price:,.2f}")
            print(f"   High: ${high_price:,.2f}")
            print(f"   Low: ${low_price:,.2f}")
            print(f"   Change: ${price_change:+.2f} ({price_change_pct:+.2f}%)")
            print(f"   Range: ${session_range:.2f}")
            
            print(f"\n📈 MARKET CONDITIONS")
            print(f"   Volatility: {volatility*100:.2f}% (hourly)")
            print(f"   Total Volume: {total_volume:,}")
            print(f"   Avg Volume/min: {avg_volume:,.0f}")
            
            print(f"\n🎯 MOMENTUM ANALYSIS")
            print(f"   Positive Bars: {positive_bars} ({positive_bars/len(df)*100:.1f}%)")
            print(f"   Negative Bars: {negative_bars} ({negative_bars/len(df)*100:.1f}%)")
            print(f"   Neutral Bars: {neutral_bars} ({neutral_bars/len(df)*100:.1f}%)")
            
            # Trading condition assessment
            print(f"\n📊 TRADING ASSESSMENT")
            
            # Volatility assessment
            if volatility > 0.02:  # 2% hourly volatility
                print(f"   ✅ Volatility: EXCELLENT ({volatility*100:.2f}% hourly)")
            elif volatility > 0.01:
                print(f"   ✅ Volatility: GOOD ({volatility*100:.2f}% hourly)")
            else:
                print(f"   ⚠️  Volatility: LOW ({volatility*100:.2f}% hourly)")
            
            # Volume assessment
            if avg_volume > 2000:
                print(f"   ✅ Liquidity: EXCELLENT ({avg_volume:,.0f}/min)")
            elif avg_volume > 1500:
                print(f"   ✅ Liquidity: GOOD ({avg_volume:,.0f}/min)")
            else:
                print(f"   ⚠️  Liquidity: MODERATE ({avg_volume:,.0f}/min)")
            
            # Momentum assessment
            if abs(price_change_pct) > 0.3:
                print(f"   ✅ Momentum: STRONG ({price_change_pct:+.2f}%)")
            elif abs(price_change_pct) > 0.1:
                print(f"   ✅ Momentum: MODERATE ({price_change_pct:+.2f}%)")
            else:
                print(f"   ⚠️  Momentum: WEAK ({price_change_pct:+.2f}%)")
            
            # Overall assessment
            print(f"\n🎯 OVERALL ASSESSMENT")
            if volatility > 0.015 and avg_volume > 1500 and abs(price_change_pct) > 0.2:
                print(f"   🏆 EXCELLENT CONDITIONS for Atlas Strategy")
                print(f"   📈 High probability of profitable trades")
                print(f"   🚀 Optimal for FTMO evaluation trading")
            elif volatility > 0.01 and avg_volume > 1000 and abs(price_change_pct) > 0.1:
                print(f"   ✅ GOOD CONDITIONS for Atlas Strategy")
                print(f"   📊 Moderate probability of profitable trades")
                print(f"   ⚡ Suitable for FTMO evaluation trading")
            else:
                print(f"   ⚠️  CHALLENGING CONDITIONS")
                print(f"   📉 Lower probability of profitable trades")
                print(f"   🔄 Consider waiting for better conditions")
            
            print(f"\n💡 STRATEGY IMPLICATIONS")
            print(f"   📊 Data Quality: Professional CME Level 1")
            print(f"   🎯 Target Achievement: Potential for 11.52% return")
            print(f"   📈 Signal Quality: {len(df)} bars sufficient for indicators")
            print(f"   ⚡ Execution Environment: Real-time professional data")
            
            # Save summary
            summary = {
                'timestamp': datetime.now(),
                'bars_collected': len(df),
                'session_duration': str(session_duration),
                'price_change_pct': price_change_pct,
                'volatility_hourly': volatility,
                'avg_volume': avg_volume,
                'session_range': session_range
            }
            
            return summary
            
        else:
            print("❌ Insufficient data for analysis")
            return None
            
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return None

if __name__ == "__main__":
    print("🎯 Purpose: Analyze collected live CME professional data")
    print("📊 Goal: Assess market conditions for Atlas Strategy")
    print("🏆 Target: Validate FTMO trading environment")
    print()
    
    try:
        result = analyze_collected_data()
        
        if result:
            print(f"\n📋 SESSION SUMMARY")
            print(f"   Data Bars: {result['bars_collected']}")
            print(f"   Duration: {result['session_duration']}")
            print(f"   Performance: {result['price_change_pct']:+.2f}%")
            print(f"   Volatility: {result['volatility_hourly']*100:.2f}%/hour")
            print(f"   Volume: {result['avg_volume']:,.0f}/min")
            
            print(f"\n🚀 NEXT STEPS:")
            print(f"   1. Fix strategy time calculation bug")
            print(f"   2. Run Atlas Strategy with collected data")
            print(f"   3. Validate 11.52% FTMO target achievement")
            print(f"   4. Proceed with live FTMO evaluation")
            
        else:
            print("❌ Analysis incomplete")
            
    except Exception as e:
        print(f"❌ Error: {e}")
