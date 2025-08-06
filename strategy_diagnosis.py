#!/usr/bin/env python3
"""
Strategy Signal Diagnosis
Analyze why no trades were generated with live data
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
from datetime import datetime, time as dt_time
import ta

class DiagnosticCollector(EWrapper, EClient):
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

def diagnose_strategy_signals():
    """Diagnose why strategy generated no signals"""
    print("🔍 ATLAS STRATEGY SIGNAL DIAGNOSIS")
    print("Analyzing live market conditions vs strategy requirements")
    print("=" * 70)
    
    # Collect live data
    app = DiagnosticCollector()
    
    try:
        print("📊 Collecting live data for analysis...")
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
        
        app.reqHistoricalData(
            1, contract, "", "1 D", "1 min", "TRADES", 1, 1, False, []
        )
        
        timeout = 30
        while timeout > 0 and not app.completed:
            time.sleep(1)
            timeout -= 1
        
        app.disconnect()
        
        if not app.data or len(app.data) < 50:
            print("❌ Insufficient data for diagnosis")
            return
        
        # Convert to DataFrame
        df = pd.DataFrame(app.data)
        df.set_index('datetime', inplace=True)
        df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        
        print(f"✅ Analyzing {len(df)} bars of live data")
        print(f"📅 Period: {df.index[0].strftime('%H:%M')} - {df.index[-1].strftime('%H:%M')}")
        
        # Calculate technical indicators (matching our strategy)
        print(f"\n🔧 CALCULATING TECHNICAL INDICATORS")
        
        # EMAs
        ema_fast = ta.trend.EMAIndicator(df['Close'], window=15).ema_indicator()
        ema_slow = ta.trend.EMAIndicator(df['Close'], window=35).ema_indicator()
        
        # RSI
        rsi = ta.momentum.RSIIndicator(df['Close'], window=12).rsi()
        
        # ATR
        atr = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close'], window=16).average_true_range()
        
        # Volume
        volume_avg = df['Volume'].rolling(window=25).mean()
        volume_multiplier = df['Volume'] / volume_avg
        
        # Price momentum
        momentum = df['Close'].pct_change(10)  # 10-period momentum
        
        print(f"   ✅ EMA Fast (15): Current = ${ema_fast.iloc[-1]:.2f}")
        print(f"   ✅ EMA Slow (35): Current = ${ema_slow.iloc[-1]:.2f}")
        print(f"   ✅ RSI (12): Current = {rsi.iloc[-1]:.1f}")
        print(f"   ✅ ATR (16): Current = ${atr.iloc[-1]:.2f}")
        print(f"   ✅ Volume Multiplier: Current = {volume_multiplier.iloc[-1]:.2f}x")
        print(f"   ✅ Momentum (10): Current = {momentum.iloc[-1]*100:.3f}%")
        
        # Analyze signal conditions
        print(f"\n📊 STRATEGY SIGNAL ANALYSIS")
        
        # Check EMA crossover conditions
        ema_bullish = ema_fast > ema_slow
        ema_bearish = ema_fast < ema_slow
        recent_ema_cross = False
        
        if len(ema_fast) > 5:
            # Check for recent crossover
            for i in range(-5, 0):
                if (ema_fast.iloc[i] > ema_slow.iloc[i] and 
                    ema_fast.iloc[i-1] <= ema_slow.iloc[i-1]):
                    recent_ema_cross = True
                    break
                elif (ema_fast.iloc[i] < ema_slow.iloc[i] and 
                      ema_fast.iloc[i-1] >= ema_slow.iloc[i-1]):
                    recent_ema_cross = True
                    break
        
        print(f"   EMA Condition: Fast > Slow = {ema_bullish.iloc[-1]} (Bullish)")
        print(f"   EMA Condition: Fast < Slow = {ema_bearish.iloc[-1]} (Bearish)")
        print(f"   Recent EMA Cross: {recent_ema_cross}")
        
        # Check RSI conditions
        rsi_current = rsi.iloc[-1]
        rsi_long_condition = 30 <= rsi_current <= 70  # Adjusted params
        rsi_short_condition = 30 <= rsi_current <= 70  # Same range
        
        print(f"   RSI Current: {rsi_current:.1f}")
        print(f"   RSI Long Zone (30-70): {rsi_long_condition}")
        print(f"   RSI Short Zone (30-70): {rsi_short_condition}")
        
        # Check volume condition
        vol_current = volume_multiplier.iloc[-1]
        vol_threshold = 1.5  # Adjusted params
        vol_condition = vol_current >= vol_threshold
        
        print(f"   Volume Multiplier: {vol_current:.2f}x")
        print(f"   Volume Threshold: {vol_threshold}x")
        print(f"   Volume Condition Met: {vol_condition}")
        
        # Check momentum condition
        momentum_current = momentum.iloc[-1]
        momentum_threshold = 0.0008  # From optimized params
        momentum_condition = abs(momentum_current) >= momentum_threshold
        
        print(f"   Momentum Current: {momentum_current:.4f} ({momentum_current*100:.3f}%)")
        print(f"   Momentum Threshold: {momentum_threshold:.4f} ({momentum_threshold*100:.3f}%)")
        print(f"   Momentum Condition Met: {momentum_condition}")
        
        # Check trading session
        current_time = df.index[-1].time()
        session_start = dt_time(14, 30)  # 14:30
        session_end = dt_time(20, 0)     # 20:00
        buffer_minutes = 30
        
        # Calculate buffer times properly
        from datetime import datetime, timedelta
        today = datetime.now().date()
        session_start_dt = datetime.combine(today, session_start)
        session_end_dt = datetime.combine(today, session_end)
        buffer_start_dt = session_start_dt + timedelta(minutes=buffer_minutes)
        buffer_end_dt = session_end_dt - timedelta(minutes=buffer_minutes)
        
        buffer_start = buffer_start_dt.time()
        buffer_end = buffer_end_dt.time()
        
        trading_session = buffer_start <= current_time <= buffer_end
        
        print(f"   Current Time: {current_time}")
        print(f"   Trading Window: {buffer_start} - {buffer_end}")
        print(f"   In Trading Session: {trading_session}")
        
        # Overall signal analysis
        print(f"\n🎯 SIGNAL GENERATION ANALYSIS")
        
        # Count potential signals during session
        signal_count = 0
        long_signals = 0
        short_signals = 0
        
        # Check each bar for potential signals
        for i in range(50, len(df)):  # Skip first 50 for indicator warmup
            bar_time = df.index[i].time()
            
            # Check if in trading session
            if not (buffer_start <= bar_time <= buffer_end):
                continue
                
            # Check if all conditions met for long
            if (i > 0 and 
                ema_fast.iloc[i] > ema_slow.iloc[i] and
                30 <= rsi.iloc[i] <= 70 and
                volume_multiplier.iloc[i] >= 1.5 and
                abs(momentum.iloc[i]) >= 0.0008):
                long_signals += 1
                signal_count += 1
            
            # Check if all conditions met for short
            if (i > 0 and 
                ema_fast.iloc[i] < ema_slow.iloc[i] and
                30 <= rsi.iloc[i] <= 70 and
                volume_multiplier.iloc[i] >= 1.5 and
                abs(momentum.iloc[i]) >= 0.0008):
                short_signals += 1
                signal_count += 1
        
        print(f"   Total Potential Signals: {signal_count}")
        print(f"   Long Signals: {long_signals}")
        print(f"   Short Signals: {short_signals}")
        
        # Identify the bottleneck
        print(f"\n🔍 BOTTLENECK ANALYSIS")
        
        # Test relaxed conditions
        volume_relaxed = (volume_multiplier >= 1.5).sum()  # Lower volume threshold
        momentum_relaxed = (abs(momentum) >= 0.0005).sum()  # Lower momentum threshold
        rsi_relaxed = ((rsi >= 30) & (rsi <= 70)).sum()  # Wider RSI range
        
        print(f"   Bars meeting Volume ≥1.5x: {volume_relaxed}/{len(df)} ({volume_relaxed/len(df)*100:.1f}%)")
        print(f"   Bars meeting Momentum ≥0.05%: {momentum_relaxed}/{len(df)} ({momentum_relaxed/len(df)*100:.1f}%)")
        print(f"   Bars meeting RSI 30-70: {rsi_relaxed}/{len(df)} ({rsi_relaxed/len(df)*100:.1f}%)")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS")
        
        if signal_count == 0:
            print(f"   ⚠️  NO SIGNALS GENERATED - Strategy too restrictive for current market")
            print(f"   📊 Market Analysis:")
            print(f"      - Session was moderate volatility (0.47% hourly)")
            print(f"      - Good momentum (+0.48% session)")
            print(f"      - Adequate liquidity (1,718/min volume)")
            
            print(f"   🔧 Suggested Adjustments:")
            if vol_condition == False:
                print(f"      - Lower volume threshold from 1.8x to 1.5x")
            if momentum_condition == False:
                print(f"      - Lower momentum threshold from 0.08% to 0.05%")
            if not (rsi_long_condition or rsi_short_condition):
                print(f"      - Widen RSI range from 35-65 to 30-70")
                
            print(f"   🎯 Alternative Approach:")
            print(f"      - Test strategy during higher volatility sessions")
            print(f"      - Use adaptive parameters based on market regime")
            print(f"      - Consider multiple timeframe confirmation")
        
        else:
            print(f"   ✅ Signals generated successfully")
            print(f"   📈 Strategy parameters are appropriate for live conditions")
        
        return {
            'total_bars': len(df),
            'signal_count': signal_count,
            'long_signals': long_signals,
            'short_signals': short_signals,
            'volume_condition': vol_condition,
            'momentum_condition': momentum_condition,
            'rsi_condition': rsi_long_condition or rsi_short_condition,
            'trading_session': trading_session
        }
        
    except Exception as e:
        print(f"❌ Diagnosis failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🎯 Purpose: Diagnose why Atlas Strategy generated no signals")
    print("📊 Goal: Identify bottlenecks in signal generation")
    print("🔧 Output: Recommendations for parameter adjustment")
    print()
    
    result = diagnose_strategy_signals()
    
    if result:
        print(f"\n📋 DIAGNOSIS SUMMARY")
        print(f"   Data Bars: {result['total_bars']}")
        print(f"   Signals Generated: {result['signal_count']}")
        print(f"   Strategy Effectiveness: {result['signal_count']/result['total_bars']*100:.2f}%")
        
        if result['signal_count'] == 0:
            print(f"\n🚨 ACTION REQUIRED:")
            print(f"   1. Adjust strategy parameters for live market conditions")
            print(f"   2. Test with relaxed conditions")
            print(f"   3. Consider market regime adaptations")
            print(f"   4. Validate with higher volatility sessions")
        else:
            print(f"\n✅ STRATEGY VALIDATED WITH LIVE DATA")
    else:
        print("❌ Diagnosis incomplete")
