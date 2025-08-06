#!/usr/bin/env python3
"""
Real-Time Strategy Test
Test our optimized strategy with live CME data
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
import backtrader as bt
from datetime import datetime, timedelta
import numpy as np

# Import our optimized strategy
from src.strategies.atlas_momentum import AtlasMomentumStrategy

class RealTimeDataApp(EWrapper, EClient):
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

def collect_realtime_nq():
    """Collect real-time NQ data"""
    print("🔴 COLLECTING LIVE CME DATA")
    print("=" * 40)
    
    app = RealTimeDataApp()
    
    try:
        # Connect
        print("🔌 Connecting to IB TWS...")
        app.connect("127.0.0.1", 7497, 0)
        
        thread = threading.Thread(target=app.run, daemon=True)
        thread.start()
        time.sleep(2)
        
        # NQ Contract (working config)
        contract = Contract()
        contract.symbol = "NQ"
        contract.secType = "FUT"
        contract.exchange = "CME"
        contract.currency = "USD"
        contract.lastTradeDateOrContractMonth = "20250919"
        
        print("📊 Requesting live NQ data (1 day)...")
        
        # Get 1 day of data (format that works)
        app.reqHistoricalData(
            1, contract, "", "1 D", "1 min", "TRADES", 1, 1, False, []
        )
        
        # Wait for data
        timeout = 30
        while timeout > 0 and not app.completed:
            time.sleep(1)
            timeout -= 1
            if timeout % 5 == 0:
                print(f"   📈 {len(app.data)} bars collected...")
        
        if app.data:
            df = pd.DataFrame(app.data)
            df.set_index('datetime', inplace=True)
            df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            
            print(f"✅ Got {len(df)} live bars")
            print(f"💰 Current NQ: ${df['Close'].iloc[-1]:.2f}")
            print(f"📊 Period: {df.index[0].strftime('%H:%M')} - {df.index[-1].strftime('%H:%M')}")
            
            return df
        else:
            print("❌ No data received")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None
    finally:
        app.disconnect()

class LivePandasData(bt.feeds.PandasData):
    """Live data feed"""
    params = (
        ('datetime', None),
        ('open', 'Open'),
        ('high', 'High'), 
        ('low', 'Low'),
        ('close', 'Close'),
        ('volume', 'Volume'),
        ('openinterest', None),
    )

def test_strategy_live():
    """Test our strategy with live data"""
    print("\n🚀 TESTING ATLAS STRATEGY")
    print("=" * 40)
    
    # Get live data
    df = collect_realtime_nq()
    if df is None or len(df) < 5:  # Need at least 5 bars
        print("❌ Insufficient data for testing")
        return
    
    print(f"🧪 Testing on {len(df)} live bars...")
    
    # Setup Backtrader
    cerebro = bt.Cerebro()
    
    # Import optimized configuration
    from ftmo_ready_config import get_ftmo_optimized_config
    config = get_ftmo_optimized_config()
    
    # Add strategy with adjusted parameters for moderate volatility
    cerebro.addstrategy(AtlasMomentumStrategy,
                       # RSI Parameters
                       rsi_long_min=config['rsi_lower'],        # 30
                       rsi_long_max=config['rsi_upper'],        # 70
                       rsi_short_min=config['rsi_lower'],       # 30
                       rsi_short_max=config['rsi_upper'],       # 70
                       rsi_period=config['rsi_period'],         # 12
                       
                       # Volume Parameters  
                       volume_multiplier=config['volume_threshold'],  # 0.6 (adjusted)
                       
                       # Volatility Parameters
                       atr_multiplier=config['atr_multiplier'], # 0.8 (adjusted)
                       bb_percentile=config['bb_percentile'],   # 50 (adjusted)
                       
                       # EMA Parameters
                       ema_fast=config['ema_fast'],             # 15
                       ema_slow=config['ema_slow'],             # 35
                       atr_period=config['atr_period'],         # 16
                       
                       # Risk Management
                       stop_loss_atr_mult=config['atr_stop_multiplier'],  # 2.5
                       reward_risk_ratio=config['risk_reward_ratio'])     # 3.0
    
    # Add live data
    data = LivePandasData(dataname=df)
    cerebro.adddata(data)
    
    # FTMO settings
    cerebro.broker.setcash(50000)  # £50k
    cerebro.broker.setcommission(commission=0.62, margin=2000, mult=20)
    
    # Add analyzers
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='dd')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    
    print("💰 Capital: £50,000 (FTMO)")
    print("📊 Commission: £0.62 per side")
    print("🔄 Running strategy...")
    
    # Run
    start_value = cerebro.broker.getvalue()
    results = cerebro.run()
    end_value = cerebro.broker.getvalue()
    
    # Results
    strategy = results[0]
    pnl = end_value - start_value
    pnl_pct = (pnl / start_value) * 100
    
    trades = strategy.analyzers.trades.get_analysis()
    dd = strategy.analyzers.dd.get_analysis()
    
    print("\n" + "=" * 50)
    print("🏆 LIVE TEST RESULTS")
    print("=" * 50)
    
    print(f"💰 P&L: £{pnl:.2f} ({pnl_pct:+.2f}%)")
    print(f"📊 Data: {len(df)} live CME bars")
    print(f"⏰ Period: {df.index[-1] - df.index[0]}")
    
    if trades.get('total', {}).get('total', 0) > 0:
        total = trades['total']['total']
        won = trades['won']['total'] if 'won' in trades else 0
        win_rate = (won / total) * 100
        
        print(f"📈 Trades: {total} ({win_rate:.1f}% win rate)")
        
        if 'won' in trades and 'pnl' in trades['won']:
            avg_win = trades['won']['pnl']['average']
            print(f"✅ Avg Win: £{avg_win:.2f}")
            
        if 'lost' in trades and 'pnl' in trades['lost']:
            avg_loss = trades['lost']['pnl']['average']
            print(f"❌ Avg Loss: £{avg_loss:.2f}")
    else:
        print("📈 Trades: 0 (no signals)")
    
    max_dd = dd.get('max', {}).get('drawdown', 0)
    print(f"📉 Max DD: {max_dd:.2f}%")
    
    # FTMO check
    ftmo_ok = max_dd < 10 and pnl_pct > 0
    
    if ftmo_ok:
        print("\n🎯 FTMO STATUS: ✅ PASS")
        if pnl_pct > 10:
            print(f"🏆 EXCELLENT: {pnl_pct:.2f}% > 10% target!")
        else:
            print(f"✅ GOOD: {pnl_pct:.2f}% profit")
    else:
        print("\n🎯 FTMO STATUS: ❌ FAIL")
        if max_dd >= 10:
            print(f"❌ Drawdown too high: {max_dd:.2f}%")
        if pnl_pct <= 0:
            print(f"❌ No profit: {pnl_pct:.2f}%")
    
    # Current time extrapolation
    hours_tested = (df.index[-1] - df.index[0]).total_seconds() / 3600
    if hours_tested > 0:
        hourly_return = pnl_pct / hours_tested
        daily_return = hourly_return * 8  # 8-hour trading day
        monthly_return = daily_return * 22  # 22 trading days
        
        print(f"\n📊 EXTRAPOLATION:")
        print(f"   Hourly: {hourly_return:+.3f}%")
        print(f"   Daily: {daily_return:+.2f}%")
        print(f"   Monthly: {monthly_return:+.1f}%")
        
        if monthly_return > 10:
            print(f"🎯 Projected FTMO target achievement!")
    
    return {
        'pnl_pct': pnl_pct,
        'max_dd': max_dd,
        'trades': trades.get('total', {}).get('total', 0),
        'ftmo_pass': ftmo_ok,
        'data_bars': len(df)
    }

if __name__ == "__main__":
    print("🔴 LIVE MARKET TEST")
    print("Professional CME Data + Optimized Strategy")
    print("Target: FTMO £50k evaluation")
    print("=" * 50)
    
    try:
        result = test_strategy_live()
        
        if result:
            print(f"\n🎯 SUMMARY:")
            print(f"   Return: {result['pnl_pct']:+.2f}%")
            print(f"   Drawdown: {result['max_dd']:.2f}%") 
            print(f"   Trades: {result['trades']}")
            print(f"   FTMO Ready: {'YES' if result['ftmo_pass'] else 'NO'}")
            print(f"   Data Quality: {result['data_bars']} live CME bars")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
