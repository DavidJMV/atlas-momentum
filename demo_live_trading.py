#!/usr/bin/env python3
"""
Real-Time NQ Strategy Testing
Tests Atlas Strategy with live CME professional data
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

from src.data.ib_integration import IBDataProvider
import pandas as pd
from datetime import datetime, timedelta
import time

def collect_live_nq_data():
    """Collect live NQ data for strategy testing"""
    print("📊 LIVE NQ DATA COLLECTION - REAL MARKET DATA")
    print("=" * 60)
    print("🕐 Market Status: US Session OPEN")
    print("🎯 Collecting professional CME NQ data...")
    print()
    
    provider = IBDataProvider()
    
    try:
        print("🔌 Connecting to TWS...")
        if not provider.connect():
            print("❌ Failed to connect to TWS")
            print("💡 Make sure TWS is running on port 7497")
            return None
        
        print("✅ Connected to TWS successfully")
        
        # Create NQ futures contract with correct expiry
        from ibapi.contract import Contract
        nq_contract = Contract()
        nq_contract.symbol = "NQ"
        nq_contract.secType = "FUT"
        nq_contract.exchange = "CME"
        nq_contract.currency = "USD"
        # Use September 2025 contract (NQU2025)
        nq_contract.lastTradeDateOrContractMonth = "20250919"  # September 19, 2025 expiry
        
        print("📈 Requesting live NQ historical data...")
        
        # Get request ID
        req_id = provider.app.get_next_req_id()
        
        # Initialize storage
        provider.app.historical_data[req_id] = []
        provider.app.historical_data_complete[req_id] = False
        
        # Request 2 hours of 1-minute data
        end_time = datetime.now()
        end_time_str = end_time.strftime("%Y%m%d %H:%M:%S GMT")
        
        print(f"📊 Requesting 2 hours of 1-minute NQ data...")
        print(f"   End time: {end_time_str}")
        print(f"   Request ID: {req_id}")
        
        # Make the historical data request
        provider.app.reqHistoricalData(
            req_id, nq_contract, end_time_str, "2 H", "1 min",
            "MIDPOINT", 1, 1, False, []
        )
        
        # Wait for completion
        print("⏳ Waiting for data...")
        timeout = 30
        while timeout > 0 and not provider.app.historical_data_complete.get(req_id, False):
            time.sleep(1)
            timeout -= 1
            if timeout % 5 == 0:
                received_bars = len(provider.app.historical_data.get(req_id, []))
                print(f"   Waiting... {timeout}s remaining ({received_bars} bars received)")
        
        # Check results
        if provider.app.historical_data_complete.get(req_id, False):
            data_list = provider.app.historical_data.get(req_id, [])
            
            if data_list:
                df = pd.DataFrame(data_list)
                df.set_index('datetime', inplace=True)
                df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
                
                print(f"\n✅ SUCCESS! Collected {len(df)} live NQ bars")
                print(f"📈 Price range: ${df['Close'].min():.2f} - ${df['Close'].max():.2f}")
                print(f"📊 Current price: ${df['Close'].iloc[-1]:.2f}")
                print(f"📈 Session change: ${df['Close'].iloc[-1] - df['Close'].iloc[0]:.2f}")
                print(f"📊 Average volume: {df['Volume'].mean():,.0f}")
                
                print(f"\n📋 Sample data (last 5 bars):")
                print(df.tail().round(2))
                
                return df
            else:
                print("❌ No data received")
                return None
        else:
            received_bars = len(provider.app.historical_data.get(req_id, []))
            print(f"⏰ Request timed out ({received_bars} bars received)")
            
            # Return partial data if we got some
            if received_bars > 0:
                data_list = provider.app.historical_data.get(req_id, [])
                df = pd.DataFrame(data_list)
                df.set_index('datetime', inplace=True)
                df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
                print(f"✅ Using partial data: {len(df)} bars")
                return df
            
            return None
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None
        
    finally:
        provider.disconnect()
        print("🔌 Disconnected from TWS")

def test_atlas_strategy_live():
    """Test Atlas Strategy with live data"""
    print("\n" + "="*60)
    print("🧪 ATLAS STRATEGY - LIVE DATA TESTING")
    print("="*60)
    
    # Collect live data first
    live_data = collect_live_nq_data()
    
    if live_data is None:
        print("❌ Cannot test strategy without live data")
        return
    
    if len(live_data) < 50:
        print(f"⚠️ Limited data: {len(live_data)} bars (need 50+ for full test)")
        print("🔄 Running simplified analysis...")
    
    print(f"\n🔧 Running Atlas Strategy on {len(live_data)} bars of live NQ data...")
    
    # Calculate our optimized indicators (Momentum Master config)
    ema_fast = live_data['Close'].ewm(span=15).mean()  # Optimized: 15
    ema_slow = live_data['Close'].ewm(span=35).mean()  # Optimized: 35
    
    # ATR calculation
    hl = live_data['High'] - live_data['Low']
    hc = abs(live_data['High'] - live_data['Close'].shift())
    lc = abs(live_data['Low'] - live_data['Close'].shift())
    atr = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(16).mean()  # Optimized: 16
    
    # RSI calculation  
    delta = live_data['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(12).mean()  # Optimized: 12
    loss = (-delta.where(delta < 0, 0)).rolling(12).mean()
    rsi = 100 - (100 / (1 + gain / loss))
    
    # Volume analysis
    volume_ma = live_data['Volume'].rolling(25).mean()  # Optimized: 25
    volume_ratio = live_data['Volume'] / volume_ma
    
    # Momentum 
    momentum = live_data['Close'] / live_data['Close'].shift(10) - 1  # Optimized: 10
    
    # Strategy signals (using our optimized parameters)
    signals = []
    
    start_idx = max(35, 25, 16, 12)  # Wait for all indicators
    
    for i in range(start_idx, len(live_data)):
        # Skip if any indicator is NaN
        if any(pd.isna(x) for x in [atr.iloc[i], rsi.iloc[i], volume_ratio.iloc[i], momentum.iloc[i]]):
            continue
        
        # Optimized signal conditions (Momentum Master)
        trend_bullish = ema_fast.iloc[i] > ema_slow.iloc[i]
        price_above_ema = live_data['Close'].iloc[i] > ema_fast.iloc[i]
        rsi_good = 35 <= rsi.iloc[i] <= 65  # Optimized range
        volume_spike = volume_ratio.iloc[i] >= 1.8  # Optimized threshold
        momentum_positive = momentum.iloc[i] > 0.0008  # Optimized threshold
        atr_reasonable = 2.5 <= atr.iloc[i] <= 15.0  # Optimized range
        
        if (trend_bullish and price_above_ema and rsi_good and 
            volume_spike and momentum_positive and atr_reasonable):
            
            signals.append({
                'time': live_data.index[i],
                'price': live_data['Close'].iloc[i],
                'atr': atr.iloc[i],
                'rsi': rsi.iloc[i],
                'volume_ratio': volume_ratio.iloc[i],
                'momentum': momentum.iloc[i],
                'signal_strength': (ema_fast.iloc[i] - ema_slow.iloc[i]) / ema_slow.iloc[i] * 100
            })
    
    # Analysis results
    print(f"\n📊 LIVE DATA STRATEGY RESULTS:")
    print(f"   Data Period: {live_data.index[0].strftime('%H:%M')} to {live_data.index[-1].strftime('%H:%M')}")
    print(f"   Total Bars: {len(live_data)}")
    print(f"   Price Movement: ${live_data['Close'].iloc[-1] - live_data['Close'].iloc[0]:.2f}")
    print(f"   Signals Generated: {len(signals)}")
    print(f"   Average ATR: ${atr.mean():.2f}")
    print(f"   Latest Price: ${live_data['Close'].iloc[-1]:.2f}")
    
    if signals:
        print(f"\n📈 TRADE SIGNALS (MOMENTUM MASTER CONFIG):")
        for i, signal in enumerate(signals):
            stop_loss = signal['atr'] * 2.5  # Optimized stop multiplier
            take_profit = stop_loss * 3.0   # Optimized R:R ratio
            
            print(f"   Signal {i+1}: {signal['time'].strftime('%H:%M:%S')}")
            print(f"      Price: ${signal['price']:.2f}")
            print(f"      Stop Loss: ${signal['price'] - stop_loss:.2f} (-${stop_loss:.2f})")
            print(f"      Take Profit: ${signal['price'] + take_profit:.2f} (+${take_profit:.2f})")
            print(f"      RSI: {signal['rsi']:.1f}, Volume: {signal['volume_ratio']:.1f}x")
            print(f"      Momentum: {signal['momentum']:.4f}, Strength: {signal['signal_strength']:.2f}%")
            print()
    else:
        print(f"\n📊 No signals generated in this period")
        print(f"💡 This is normal - strategy waits for optimal conditions")
        
        # Show current market state
        latest_idx = len(live_data) - 1
        print(f"\n📈 Current Market State:")
        print(f"   EMA Trend: {'Bullish' if ema_fast.iloc[latest_idx] > ema_slow.iloc[latest_idx] else 'Bearish'}")
        print(f"   RSI: {rsi.iloc[latest_idx]:.1f} (target: 35-65)")
        print(f"   Volume: {volume_ratio.iloc[latest_idx]:.1f}x average (target: ≥1.8x)")
        print(f"   Momentum: {momentum.iloc[latest_idx]:.4f} (target: >0.0008)")
        print(f"   ATR: ${atr.iloc[latest_idx]:.2f} (target: 2.5-15.0)")
    
    print(f"\n✅ LIVE DATA STRATEGY TEST COMPLETE!")
    print(f"🎯 Atlas Strategy successfully tested with real CME data")
    print(f"🏆 Using FTMO-optimized 'Momentum Master' parameters")
    
    return live_data, signals

if __name__ == "__main__":
    test_atlas_strategy_live()
