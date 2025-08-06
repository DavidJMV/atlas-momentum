#!/usr/bin/env python3
"""
Complete Atlas Strategy Diagnosis
Analyzes ALL strategy conditions including volatility expansion,
volume confirmation, and Bollinger Band width
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
import ta

print("🔍 COMPLETE ATLAS STRATEGY DIAGNOSIS")
print("Analyzing ALL strategy conditions with live data")
print("=" * 70)

class DataApp(EWrapper, EClient):
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

def analyze_complete_strategy():
    """Complete analysis of all strategy conditions"""
    
    print("📊 Collecting live data for complete analysis...")
    
    app = DataApp()
    app.connect("127.0.0.1", 7497, 1)
    
    def run_loop():
        app.run()
    
    api_thread = threading.Thread(target=run_loop, daemon=True)
    api_thread.start()
    
    time.sleep(2)
    
    # NQ December 2024 contract
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
        print("❌ Insufficient data for complete analysis")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(app.data)
    df.set_index('datetime', inplace=True)
    df = df.sort_index()
    
    print(f"✅ Analyzing {len(df)} bars of live data")
    print(f"📅 Period: {df.index[0].strftime('%H:%M')} - {df.index[-1].strftime('%H:%M')}")
    
    # Calculate ALL technical indicators used by strategy
    print(f"\n🔧 CALCULATING ALL TECHNICAL INDICATORS")
    
    # EMAs
    ema_fast = ta.trend.EMAIndicator(df['close'], window=15).ema_indicator()
    ema_slow = ta.trend.EMAIndicator(df['close'], window=35).ema_indicator()
    
    # RSI
    rsi = ta.momentum.RSIIndicator(df['close'], window=12).rsi()
    
    # ATR (current and average)
    atr = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'], window=16).average_true_range()
    atr_avg = atr.rolling(window=16).mean()
    
    # Volume (current and average)
    volume_avg = df['volume'].rolling(window=25).mean()
    volume_multiplier = df['volume'] / volume_avg
    
    # Bollinger Bands
    bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
    bb_upper = bb.bollinger_hband()
    bb_lower = bb.bollinger_lband()
    bb_width = (bb_upper - bb_lower) / df['close'] * 100
    bb_width_percentile = bb_width.rolling(window=50).rank(pct=True) * 100
    
    # Current values
    current_price = df['close'].iloc[-1]
    current_ema_fast = ema_fast.iloc[-1]
    current_ema_slow = ema_slow.iloc[-1]
    current_rsi = rsi.iloc[-1]
    current_atr = atr.iloc[-1]
    current_atr_avg = atr_avg.iloc[-1]
    current_volume = df['volume'].iloc[-1]
    current_volume_avg = volume_avg.iloc[-1]
    current_volume_mult = volume_multiplier.iloc[-1]
    current_bb_width = bb_width.iloc[-1]
    current_bb_width_percentile = bb_width_percentile.iloc[-1]
    
    print(f"   ✅ EMA Fast (15): ${current_ema_fast:.2f}")
    print(f"   ✅ EMA Slow (35): ${current_ema_slow:.2f}")
    print(f"   ✅ RSI (12): {current_rsi:.1f}")
    print(f"   ✅ ATR Current: ${current_atr:.2f}")
    print(f"   ✅ ATR Average: ${current_atr_avg:.2f}")
    print(f"   ✅ Volume Current: {current_volume:,}")
    print(f"   ✅ Volume Average: {current_volume_avg:,.0f}")
    print(f"   ✅ Volume Multiplier: {current_volume_mult:.2f}x")
    print(f"   ✅ BB Width: {current_bb_width:.3f}%")
    print(f"   ✅ BB Width Percentile: {current_bb_width_percentile:.1f}%")
    
    # Strategy parameter analysis
    print(f"\n📊 COMPLETE STRATEGY CONDITION ANALYSIS")
    
    # Parameters (from config)
    atr_multiplier = 1.2
    volume_threshold = 1.5  # Adjusted
    rsi_min = 30  # Adjusted
    rsi_max = 70  # Adjusted
    bb_percentile_threshold = 75.0
    
    # Condition 1: Trading session
    current_time = df.index[-1].time()
    session_start = "15:00"  # Adjusted for buffer
    session_end = "19:30"
    in_session = "15:00" <= current_time.strftime("%H:%M") <= "19:30"
    print(f"   Trading Session (15:00-19:30): {in_session}")
    
    # Condition 2: Volatility expansion
    volatility_expansion = current_atr > (atr_multiplier * current_atr_avg)
    print(f"   Volatility Expansion (ATR > {atr_multiplier}x avg): {volatility_expansion}")
    print(f"      Current ATR: ${current_atr:.2f} vs Required: ${atr_multiplier * current_atr_avg:.2f}")
    
    # Condition 3: Volume confirmation
    volume_confirmation = current_volume_mult >= volume_threshold
    print(f"   Volume Confirmation (≥{volume_threshold}x): {volume_confirmation}")
    print(f"      Current: {current_volume_mult:.2f}x vs Required: {volume_threshold}x")
    
    # Condition 4: Bollinger Band width
    bb_width_condition = current_bb_width_percentile > bb_percentile_threshold
    print(f"   BB Width Condition (>{bb_percentile_threshold}%): {bb_width_condition}")
    print(f"      Current: {current_bb_width_percentile:.1f}% vs Required: >{bb_percentile_threshold}%")
    
    # Condition 5: EMA trend
    ema_bullish = current_ema_fast > current_ema_slow
    ema_bearish = current_ema_fast < current_ema_slow
    print(f"   EMA Trend Bullish (Fast > Slow): {ema_bullish}")
    print(f"   EMA Trend Bearish (Fast < Slow): {ema_bearish}")
    
    # Condition 6: RSI range
    rsi_in_range = rsi_min <= current_rsi <= rsi_max
    print(f"   RSI in Range ({rsi_min}-{rsi_max}): {rsi_in_range}")
    print(f"      Current RSI: {current_rsi:.1f}")
    
    # Condition 7: Price relative to EMA
    price_above_ema = current_price > current_ema_fast
    price_below_ema = current_price < current_ema_fast
    print(f"   Price > EMA Fast: {price_above_ema}")
    print(f"   Price < EMA Fast: {price_below_ema}")
    
    # Complete signal analysis
    print(f"\n🎯 COMPLETE SIGNAL ANALYSIS")
    
    # Long signal requirements
    long_possible = (in_session and volatility_expansion and volume_confirmation and 
                    bb_width_condition and ema_bullish and rsi_in_range and price_above_ema)
    
    # Short signal requirements  
    short_possible = (in_session and volatility_expansion and volume_confirmation and
                     bb_width_condition and ema_bearish and rsi_in_range and price_below_ema)
    
    print(f"   LONG Signal Possible: {long_possible}")
    print(f"   SHORT Signal Possible: {short_possible}")
    
    # Bottleneck identification
    print(f"\n🔍 BOTTLENECK IDENTIFICATION")
    conditions = {
        "Trading Session": in_session,
        "Volatility Expansion": volatility_expansion, 
        "Volume Confirmation": volume_confirmation,
        "BB Width Condition": bb_width_condition,
        "EMA Trend": ema_bullish or ema_bearish,
        "RSI Range": rsi_in_range,
        "Price vs EMA": price_above_ema or price_below_ema
    }
    
    failed_conditions = [name for name, passed in conditions.items() if not passed]
    passed_conditions = [name for name, passed in conditions.items() if passed]
    
    print(f"   ✅ Passed Conditions ({len(passed_conditions)}/7):")
    for condition in passed_conditions:
        print(f"      - {condition}")
    
    if failed_conditions:
        print(f"   ❌ Failed Conditions ({len(failed_conditions)}/7):")
        for condition in failed_conditions:
            print(f"      - {condition}")
    
    # Recommendations
    print(f"\n💡 STRATEGY ADJUSTMENT RECOMMENDATIONS")
    
    if not volatility_expansion:
        current_ratio = current_atr / current_atr_avg
        print(f"   📉 Volatility too low: {current_ratio:.2f}x (need {atr_multiplier}x)")
        print(f"      Suggestion: Lower atr_multiplier from {atr_multiplier} to {current_ratio * 0.9:.1f}")
    
    if not volume_confirmation:
        print(f"   📊 Volume too low: {current_volume_mult:.2f}x (need {volume_threshold}x)")
        print(f"      Suggestion: Lower volume_threshold from {volume_threshold} to {current_volume_mult * 0.9:.1f}")
    
    if not bb_width_condition:
        print(f"   📏 BB Width too low: {current_bb_width_percentile:.1f}% (need >{bb_percentile_threshold}%)")
        print(f"      Suggestion: Lower bb_percentile from {bb_percentile_threshold} to {max(50, current_bb_width_percentile * 0.9):.0f}")
    
    if failed_conditions:
        print(f"\n🚨 SUMMARY")
        print(f"   No signals possible with current parameters")
        print(f"   {len(failed_conditions)} out of 7 conditions failed")
        print(f"   Primary bottlenecks: {', '.join(failed_conditions[:3])}")
    else:
        print(f"\n✅ STRATEGY READY")
        print(f"   All conditions met for signal generation")

if __name__ == "__main__":
    analyze_complete_strategy()
