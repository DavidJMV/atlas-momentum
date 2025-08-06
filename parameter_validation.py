#!/usr/bin/env python3
"""
Parameter Validation Study
Scientific validation of moderate vs original parameters
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

import backtrader as bt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

print("🔬 SCIENTIFIC PARAMETER VALIDATION")
print("Testing Original vs Moderate Parameters")
print("=" * 45)

# Generate realistic test data
print("📊 Generating 1 year of realistic NQ data...")

# Create trading session dates (14:30-20:00 GMT, Mon-Fri)
start_date = datetime(2024, 1, 1, 14, 30)
end_date = datetime(2024, 12, 31, 20, 0)

dates = []
current = start_date
while current <= end_date:
    if current.weekday() < 5:  # Weekdays only
        session_start = current.replace(hour=14, minute=30)
        session_end = current.replace(hour=20, minute=0)
        
        dt = session_start
        while dt <= session_end:
            dates.append(dt)
            dt += timedelta(minutes=1)
    current += timedelta(days=1)

# Generate realistic price data
np.random.seed(42)
base_price = 16000
returns = np.random.normal(0, 0.001, len(dates))  # Base volatility

# Add volatility regimes
regime_changes = np.random.choice(len(dates), size=50, replace=False)
for change in regime_changes:
    end_regime = min(change + np.random.randint(500, 2000), len(dates))
    regime_vol = np.random.choice([0.5, 1.5, 2.0], p=[0.3, 0.5, 0.2])
    returns[change:end_regime] *= regime_vol

# Convert to prices
prices = [base_price]
for ret in returns[:-1]:
    prices.append(prices[-1] * (1 + ret))

# Create OHLCV data
df = pd.DataFrame(index=dates[:len(prices)])
df['Close'] = prices
df['Open'] = df['Close'].shift(1).fillna(df['Close'])
df['High'] = df[['Open', 'Close']].max(axis=1) * (1 + np.random.uniform(0, 0.001, len(df)))
df['Low'] = df[['Open', 'Close']].min(axis=1) * (1 - np.random.uniform(0, 0.001, len(df)))
df['Volume'] = np.random.randint(500, 3000, len(df))

print(f"✅ Generated {len(df)} bars spanning {len(df)/(5.5*60*252):.1f} years")

def test_parameters(param_type, data):
    """Test strategy with specific parameters"""
    
    print(f"\n🧪 Testing {param_type.upper()} Parameters")
    print("-" * 30)
    
    from src.strategies.atlas_momentum import AtlasMomentumStrategy
    
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(50000.0)
    cerebro.broker.setcommission(commission=0.0012)
    
    if param_type == "original":
        params = {
            'rsi_long_min': 35, 'rsi_long_max': 65,
            'rsi_short_min': 35, 'rsi_short_max': 65,
            'volume_multiplier': 1.8,    # STRICT
            'atr_multiplier': 1.2,       # STRICT
            'bb_percentile': 75          # STRICT
        }
    else:  # moderate
        params = {
            'rsi_long_min': 30, 'rsi_long_max': 70,
            'rsi_short_min': 30, 'rsi_short_max': 70,
            'volume_multiplier': 0.6,    # RELAXED
            'atr_multiplier': 0.8,       # RELAXED  
            'bb_percentile': 50          # RELAXED
        }
    
    cerebro.addstrategy(AtlasMomentumStrategy, **params)
    
    # Add data feed
    class PandasData(bt.feeds.PandasData):
        params = (
            ('datetime', None), ('open', 'Open'), ('high', 'High'),
            ('low', 'Low'), ('close', 'Close'), ('volume', 'Volume'),
            ('openinterest', None),
        )
    
    cerebro.adddata(PandasData(dataname=data))
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    
    # Run backtest
    results = cerebro.run()
    strategy = results[0]
    
    # Extract results
    final_value = cerebro.broker.getvalue()
    total_return = (final_value - 50000) / 50000 * 100
    
    trades = strategy.analyzers.trades.get_analysis()
    drawdown = strategy.analyzers.drawdown.get_analysis()
    sharpe = strategy.analyzers.sharpe.get_analysis()
    
    total_trades = getattr(trades.total, 'closed', 0) if hasattr(trades, 'total') else 0
    win_rate = (getattr(trades.won, 'total', 0) / total_trades * 100) if total_trades > 0 else 0
    max_dd = abs(getattr(drawdown.max, 'drawdown', 0)) if hasattr(drawdown, 'max') else 0
    sharpe_ratio = sharpe.get('sharperatio', 0) or 0
    
    # Annualize results
    trading_days = len(data) / (5.5 * 60)
    annual_return = total_return * (252 / trading_days)
    trades_per_day = total_trades / trading_days
    
    result = {
        'total_return': total_return,
        'annual_return': annual_return,
        'total_trades': total_trades,
        'trades_per_day': trades_per_day,
        'win_rate': win_rate,
        'max_drawdown': max_dd,
        'sharpe_ratio': sharpe_ratio
    }
    
    print(f"Total Return: {total_return:.2f}%")
    print(f"Annual Return: {annual_return:.2f}%")
    print(f"Total Trades: {total_trades}")
    print(f"Trades/Day: {trades_per_day:.2f}")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Max Drawdown: {max_dd:.2f}%")
    print(f"Sharpe Ratio: {sharpe_ratio:.2f}")
    
    return result

# Test both parameter sets
original = test_parameters("original", df)
moderate = test_parameters("moderate", df)

# Compare results
print(f"\n📊 COMPARISON ANALYSIS")
print("=" * 30)
print(f"{'Metric':<15} {'Original':<10} {'Moderate':<10} {'Difference'}")
print("-" * 50)

metrics = [
    ('Annual Return', 'annual_return', '%'),
    ('Trades/Day', 'trades_per_day', ''),
    ('Win Rate', 'win_rate', '%'),
    ('Max Drawdown', 'max_drawdown', '%'),
    ('Sharpe Ratio', 'sharpe_ratio', '')
]

for name, key, unit in metrics:
    orig_val = original[key]
    mod_val = moderate[key]
    diff = mod_val - orig_val
    print(f"{name:<15} {orig_val:<10.2f} {mod_val:<10.2f} {diff:+.2f}{unit}")

# FTMO Assessment
print(f"\n🎯 FTMO EVALUATION ASSESSMENT")
print("-" * 32)

ftmo_score = 0

# Trade frequency (critical for 30-day evaluation)
if moderate['trades_per_day'] > 0.8:
    print("✅ Adequate trade frequency for FTMO")
    ftmo_score += 2
elif original['trades_per_day'] < 0.5:
    print("⚠️  Original may have insufficient trades for FTMO")
    ftmo_score += 1

# Risk management
if moderate['max_drawdown'] <= 3.0:
    print("✅ Acceptable drawdown risk")
    ftmo_score += 1
elif moderate['max_drawdown'] > original['max_drawdown'] * 1.5:
    print("❌ Moderate params increase risk significantly")
    ftmo_score -= 1

# Performance retention
if moderate['annual_return'] >= original['annual_return'] * 0.75:
    print("✅ Reasonable performance retention")
    ftmo_score += 1

# Risk-adjusted returns
if moderate['sharpe_ratio'] >= original['sharpe_ratio'] * 0.8:
    print("✅ Risk-adjusted returns acceptable")
    ftmo_score += 1

print(f"\nFTMO Suitability Score: {ftmo_score}/5")

# Final recommendation
print(f"\n🚀 RECOMMENDATION")
print("-" * 15)

if ftmo_score >= 4:
    print("✅ USE MODERATE PARAMETERS for FTMO")
    print("   Better suited for 30-day evaluation")
elif ftmo_score >= 2:
    print("🔄 USE ADAPTIVE STRATEGY")
    print("   Switch based on market conditions")
else:
    print("⚠️  STICK WITH ORIGINAL PARAMETERS")
    print("   Moderate params compromise too much")

print(f"\n📋 IMPLEMENTATION PLAN")
print("-" * 20)
print("1. Review validation results above")
print("2. Choose parameter set based on recommendation")
print("3. Implement adaptive_strategy_config.py if needed")
print("4. Run final Monte Carlo validation")
print("5. Deploy to FTMO evaluation")

print(f"\n✅ Validation Complete!")
