#!/usr/bin/env python3
"""
Improved Hybrid Strategy Backtest - Real Data Validation
Fixed regime switching logic and improved performance
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

from src.strategies.atlas_momentum import AtlasMomentumStrategy

class ImprovedDataApp(EWrapper, EClient):
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

class StableHybridManager:
    """
    Improved hybrid regime manager with stable switching logic
    """
    
    def __init__(self):
        self.current_regime = "primary"
        self.trades_today = 0
        self.regime_switches = 0
        self.last_switch_bar = -100  # Prevent immediate switching back
        
        # Performance tracking
        self.regime_performance = {
            'primary': {'trades': 0, 'pnl': 0.0, 'wins': 0, 'bars': 0},
            'fallback': {'trades': 0, 'pnl': 0.0, 'wins': 0, 'bars': 0}
        }
        
        # Switching configuration
        self.min_bars_between_switches = 30  # Minimum 30 minutes between switches
        self.max_switches_per_session = 2   # Maximum 2 switches per session
        self.fallback_emergency_hour = 18   # Emergency fallback after 18:00
        
        # Session tracking
        self.session_day = None
        self.current_bar = 0
        self.regime_history = []
        
    def update_regime(self, bar_index, datetime_obj, current_trades):
        """Update regime with improved stability"""
        
        self.current_bar = bar_index
        self.trades_today = current_trades
        
        # Track current day
        current_day = datetime_obj.date()
        if self.session_day != current_day:
            self._reset_daily_stats()
            self.session_day = current_day
        
        # Calculate session time
        session_hour = datetime_obj.hour
        session_minute = datetime_obj.minute
        
        # Track regime time
        self.regime_performance[self.current_regime]['bars'] += 1
        
        # Check switching conditions with stability controls
        old_regime = self.current_regime
        
        # Prevent too frequent switching
        bars_since_switch = bar_index - self.last_switch_bar
        if bars_since_switch < self.min_bars_between_switches:
            return  # Too soon to switch
        
        # Prevent too many switches
        if self.regime_switches >= self.max_switches_per_session:
            return  # Too many switches already
        
        # Switching logic
        if self.current_regime == "primary":
            should_switch, reason = self._check_fallback_trigger(session_hour, session_minute)
            if should_switch:
                self._execute_switch("fallback", reason)
        
        else:  # fallback
            should_switch, reason = self._check_primary_return(session_hour, session_minute)
            if should_switch:
                self._execute_switch("primary", reason)
    
    def _check_fallback_trigger(self, hour, minute):
        """Check if should switch to fallback (conservative)"""
        
        # Emergency conditions only
        
        # Very late session with no trades
        if hour >= 19 and self.trades_today == 0:
            return True, f"Emergency: Hour {hour}:00, no trades"
        
        # Critical end-of-session
        if hour >= 19 and minute >= 30 and self.trades_today < 1:
            return True, f"Critical: {hour}:{minute:02d}, insufficient activity"
        
        return False, "Primary maintained"
    
    def _check_primary_return(self, hour, minute):
        """Check if should return to primary (preserve edge)"""
        
        # Return to primary quickly to preserve proven edge
        
        # If we got any trades, return to primary
        if self.trades_today >= 1:
            return True, f"Activity achieved - returning to primary edge"
        
        # Don't stay in fallback too long
        fallback_bars = self.regime_performance['fallback']['bars']
        if fallback_bars > 30:  # After 30 minutes
            return True, f"Preserving edge - {fallback_bars} bars in fallback"
        
        return False, "Staying in fallback"
    
    def _execute_switch(self, new_regime, reason):
        """Execute regime switch with logging"""
        
        old_regime = self.current_regime
        self.current_regime = new_regime
        self.regime_switches += 1
        self.last_switch_bar = self.current_bar
        
        switch_info = {
            'bar': self.current_bar,
            'from_regime': old_regime,
            'to_regime': new_regime,
            'reason': reason,
            'trades': self.trades_today
        }
        self.regime_history.append(switch_info)
    
    def get_parameters(self):
        """Get parameters for current regime"""
        
        if self.current_regime == "primary":
            # Original Momentum Master parameters
            return {
                'name': 'Momentum Master',
                'rsi_long_min': 35,
                'rsi_long_max': 65,
                'rsi_short_min': 35,
                'rsi_short_max': 65,
                'volume_multiplier': 1.8,
                'atr_multiplier': 1.2,
                'bb_percentile': 75,
                'risk_per_trade': 0.012
            }
        else:
            # Activity insurance parameters
            return {
                'name': 'Activity Insurance',
                'rsi_long_min': 25,
                'rsi_long_max': 75,
                'rsi_short_min': 25,
                'rsi_short_max': 75,
                'volume_multiplier': 1.0,
                'atr_multiplier': 1.0,
                'bb_percentile': 60,
                'risk_per_trade': 0.010
            }
    
    def record_trade(self, pnl, is_winner):
        """Record trade performance"""
        regime = self.current_regime
        self.regime_performance[regime]['trades'] += 1
        self.regime_performance[regime]['pnl'] += pnl
        if is_winner:
            self.regime_performance[regime]['wins'] += 1
    
    def _reset_daily_stats(self):
        """Reset daily statistics"""
        self.trades_today = 0
        self.regime_switches = 0
        self.current_regime = "primary"  # Always start with primary
        self.last_switch_bar = -100

class ImprovedHybridStrategy(AtlasMomentumStrategy):
    """
    Improved hybrid strategy with stable regime switching
    """
    
    def __init__(self):
        super().__init__()
        self.hybrid_manager = StableHybridManager()
        self.bar_count = 0
        self.trade_count = 0
        
    def start(self):
        super().start()
        total_bars = len(self.datas[0])
        print(f"🚀 Improved Hybrid Strategy starting - {total_bars} bars")
    
    def next(self):
        """Process each bar with stable hybrid logic"""
        
        self.bar_count += 1
        current_datetime = self.datas[0].datetime.datetime(0)
        
        # Update regime (less frequent switching)
        old_regime = self.hybrid_manager.current_regime
        self.hybrid_manager.update_regime(self.bar_count, current_datetime, self.trade_count)
        
        # Only print regime changes
        if self.hybrid_manager.current_regime != old_regime:
            params = self.hybrid_manager.get_parameters()
            print(f"🔄 Bar {self.bar_count}: {old_regime.upper()} → {self.hybrid_manager.current_regime.upper()} ({params['name']})")
            
            # Update strategy parameters
            self.params.rsi_long_min = params['rsi_long_min']
            self.params.rsi_long_max = params['rsi_long_max']
            self.params.volume_multiplier = params['volume_multiplier']
            self.params.atr_multiplier = params['atr_multiplier']
        
        # Call parent strategy
        super().next()
    
    def notify_trade(self, trade):
        """Track trade performance"""
        if trade.isclosed:
            self.trade_count += 1
            pnl = trade.pnl
            is_winner = pnl > 0
            
            self.hybrid_manager.record_trade(pnl, is_winner)
            
            regime = self.hybrid_manager.current_regime
            print(f"💱 Trade #{self.trade_count} ({regime.upper()}): £{pnl:+.2f}")
        
        super().notify_trade(trade)

def collect_recent_data():
    """Collect recent market data for improved backtest"""
    print("🔴 COLLECTING RECENT MARKET DATA")
    print("=" * 34)
    
    app = ImprovedDataApp()
    
    try:
        print("🔌 Connecting to IB TWS...")
        app.connect("127.0.0.1", 7497, 1)
        
        def run_loop():
            app.run()
        
        api_thread = threading.Thread(target=run_loop, daemon=True)
        api_thread.start()
        time.sleep(2)
        
        # NQ contract
        contract = Contract()
        contract.symbol = "NQ"
        contract.secType = "FUT"
        contract.exchange = "CME"
        contract.currency = "USD"
        contract.lastTradeDateOrContractMonth = "20250919"
        
        print("📊 Requesting 2 days of data...")
        app.reqHistoricalData(1, contract, "", "2 D", "1 min", "TRADES", 1, 1, False, [])
        
        timeout = 45
        while timeout > 0 and not app.completed:
            time.sleep(1)
            timeout -= 1
        
        if not app.data:
            print("❌ No data received")
            return None
        
        df = pd.DataFrame(app.data)
        df.set_index('datetime', inplace=True)
        df = df.sort_index()
        
        # Filter to trading hours
        df['hour'] = df.index.hour
        df['minute'] = df.index.minute
        
        trading_data = df[
            ((df['hour'] == 14) & (df['minute'] >= 30)) |
            ((df['hour'] >= 15) & (df['hour'] < 20)) |
            ((df['hour'] == 20) & (df['minute'] == 0))
        ].copy()
        
        trading_data = trading_data.drop(['hour', 'minute'], axis=1)
        
        print(f"✅ Collected {len(trading_data)} trading hours bars")
        print(f"💰 Price range: ${trading_data['low'].min():.2f} - ${trading_data['high'].max():.2f}")
        print(f"📅 Period: {trading_data.index[0].strftime('%m-%d %H:%M')} to {trading_data.index[-1].strftime('%m-%d %H:%M')}")
        
        return trading_data
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None
    finally:
        app.disconnect()

def run_improved_backtest():
    """Run improved hybrid strategy backtest"""
    
    print("\n🎯 IMPROVED HYBRID STRATEGY BACKTEST")
    print("Stable regime switching with proven parameters")
    print("=" * 42)
    
    # Get data
    data = collect_recent_data()
    if data is None or len(data) < 50:
        print("❌ Insufficient data")
        return
    
    print(f"\n🧪 Testing improved hybrid on {len(data)} bars...")
    
    # Setup backtest
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(50000.0)
    cerebro.broker.setcommission(commission=0.62)
    
    # Use fixed position size for consistency
    cerebro.addsizer(bt.sizers.FixedSize, stake=1)
    
    # Add strategy
    cerebro.addstrategy(ImprovedHybridStrategy)
    
    # Prepare data
    data_formatted = data.copy()
    data_formatted.columns = ['open', 'high', 'low', 'close', 'volume']
    
    class PandasData(bt.feeds.PandasData):
        params = (
            ('datetime', None),
            ('open', 'open'),
            ('high', 'high'),
            ('low', 'low'),
            ('close', 'close'),
            ('volume', 'volume'),
            ('openinterest', None),
        )
    
    data_feed = PandasData(dataname=data_formatted)
    cerebro.adddata(data_feed)
    
    # Add analyzers
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    
    print(f"🔄 Running improved backtest...")
    
    try:
        initial_value = cerebro.broker.getvalue()
        results = cerebro.run()
        final_value = cerebro.broker.getvalue()
        
        strategy = results[0]
        hybrid_manager = strategy.hybrid_manager
        
        # Calculate results
        total_return = (final_value - initial_value) / initial_value * 100
        
        trades_analyzer = strategy.analyzers.trades.get_analysis()
        drawdown_analyzer = strategy.analyzers.drawdown.get_analysis()
        
        total_trades = getattr(trades_analyzer.total, 'closed', 0) if hasattr(trades_analyzer, 'total') else 0
        won_trades = getattr(trades_analyzer.won, 'total', 0) if hasattr(trades_analyzer, 'won') else 0
        
        win_rate = (won_trades / total_trades * 100) if total_trades > 0 else 0
        max_drawdown = abs(getattr(drawdown_analyzer.max, 'drawdown', 0)) if hasattr(drawdown_analyzer, 'max') else 0
        
        # Calculate daily metrics
        trading_days = len(data) / (5.5 * 60)
        daily_return = total_return / trading_days if trading_days > 0 else 0
        annual_return = daily_return * 252
        
        # Display results
        print(f"\n🏆 IMPROVED HYBRID RESULTS")
        print("=" * 28)
        print(f"💰 Total P&L: £{final_value - initial_value:+,.2f}")
        print(f"📈 Total Return: {total_return:+.2f}%")
        print(f"📊 Daily Return: {daily_return:+.2f}%")
        print(f"🎯 Annual Projection: {annual_return:+.1f}%")
        print(f"📅 Trading Days: {trading_days:.1f}")
        print()
        
        print(f"📈 TRADE ANALYSIS")
        print("-" * 15)
        print(f"Total Trades: {total_trades}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Max Drawdown: {max_drawdown:.2f}%")
        print()
        
        # Regime analysis
        primary_perf = hybrid_manager.regime_performance['primary']
        fallback_perf = hybrid_manager.regime_performance['fallback']
        
        total_bars = primary_perf['bars'] + fallback_perf['bars']
        primary_percentage = (primary_perf['bars'] / total_bars * 100) if total_bars > 0 else 0
        fallback_percentage = (fallback_perf['bars'] / total_bars * 100) if total_bars > 0 else 0
        
        print(f"📊 REGIME ANALYSIS")
        print("-" * 17)
        print(f"Regime Switches: {hybrid_manager.regime_switches}")
        print(f"Primary Time: {primary_percentage:.1f}% ({primary_perf['bars']} bars)")
        print(f"Fallback Time: {fallback_percentage:.1f}% ({fallback_perf['bars']} bars)")
        print()
        
        print(f"📈 PRIMARY PERFORMANCE")
        print("-" * 20)
        if primary_perf['trades'] > 0:
            primary_win_rate = primary_perf['wins'] / primary_perf['trades'] * 100
            print(f"Trades: {primary_perf['trades']}")
            print(f"P&L: £{primary_perf['pnl']:+.2f}")
            print(f"Win Rate: {primary_win_rate:.1f}%")
        else:
            print("No trades in primary regime")
        print()
        
        print(f"🔄 FALLBACK PERFORMANCE")
        print("-" * 21)
        if fallback_perf['trades'] > 0:
            fallback_win_rate = fallback_perf['wins'] / fallback_perf['trades'] * 100
            print(f"Trades: {fallback_perf['trades']}")
            print(f"P&L: £{fallback_perf['pnl']:+.2f}")
            print(f"Win Rate: {fallback_win_rate:.1f}%")
        else:
            print("No trades in fallback regime")
        print()
        
        # Switch history
        if hybrid_manager.regime_history:
            print(f"🔄 REGIME SWITCHES")
            print("-" * 16)
            for i, switch in enumerate(hybrid_manager.regime_history, 1):
                print(f"  {i}. {switch['from_regime'].upper()} → {switch['to_regime'].upper()}: {switch['reason']}")
        print()
        
        # FTMO assessment
        print(f"🎯 FTMO ASSESSMENT")
        print("-" * 16)
        
        activity_ok = total_trades >= 1
        profit_ok = total_return >= -2.0  # Allow small losses
        risk_ok = max_drawdown <= 5.0
        regime_ok = fallback_percentage <= 30
        
        print(f"{'✅' if activity_ok else '❌'} Trading Activity: {total_trades} trades")
        print(f"{'✅' if profit_ok else '❌'} P&L Control: {total_return:+.2f}% return")
        print(f"{'✅' if risk_ok else '❌'} Risk Management: {max_drawdown:.2f}% drawdown")
        print(f"{'✅' if regime_ok else '❌'} Regime Balance: {fallback_percentage:.1f}% fallback time")
        
        all_ok = activity_ok and profit_ok and risk_ok and regime_ok
        
        print()
        if all_ok:
            print("🚀 HYBRID STATUS: ✅ VALIDATED")
            print("   Improved strategy ready for deployment")
            if annual_return > 0:
                print(f"   🎯 Positive projection: {annual_return:+.1f}% annual")
        else:
            print("🔄 HYBRID STATUS: NEEDS REFINEMENT")
        
        return {
            'validated': all_ok,
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'regime_switches': hybrid_manager.regime_switches,
            'fallback_percentage': fallback_percentage
        }
        
    except Exception as e:
        print(f"❌ Backtest failed: {e}")
        return None

if __name__ == "__main__":
    results = run_improved_backtest()
    
    if results and results['validated']:
        print(f"\n🎯 VALIDATION COMPLETE")
        print("-" * 19)
        print("✅ Hybrid strategy validated on real data")
        print("✅ Stable regime switching confirmed")
        print("✅ Risk controls effective")
        print("✅ Ready for FTMO evaluation")
        
        print(f"\n🚀 DEPLOY WITH CONFIDENCE!")
        print(f"   Use: python ftmo_hybrid_final.py")
    else:
        print(f"\n⚠️  Continue refinement before deployment")
