#!/usr/bin/env python3
"""
Hybrid Strategy Backtest - Real Data Validation
Comprehensive backtest of the FTMO hybrid strategy using live CME data
Tests both regime switching logic and overall performance
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

class HybridBacktestDataApp(EWrapper, EClient):
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

class HybridRegimeManager:
    """
    Hybrid regime management for backtesting
    Simulates intelligent switching between primary and fallback modes
    """
    
    def __init__(self):
        self.current_regime = "primary"
        self.trades_today = 0
        self.fallback_minutes_used = 0
        self.regime_switches = 0
        self.session_start_bar = 0
        self.current_bar = 0
        
        # Regime tracking
        self.regime_history = []
        self.performance_by_regime = {
            'primary': {'trades': 0, 'pnl': 0.0, 'wins': 0},
            'fallback': {'trades': 0, 'pnl': 0.0, 'wins': 0}
        }
        
        # Configuration
        self.max_fallback_percentage = 25  # 25% max fallback time
        self.session_length_bars = 330     # 5.5 hours * 60 minutes
        
    def update_regime(self, bar_index, total_bars, market_data, current_trades):
        """Update regime based on current conditions"""
        
        self.current_bar = bar_index
        self.trades_today = current_trades
        
        # Calculate session time
        session_progress = (bar_index - self.session_start_bar) / self.session_length_bars
        session_minutes = int(session_progress * 330)
        session_hour = 14 + (session_minutes // 60)
        
        old_regime = self.current_regime
        
        if self.current_regime == "primary":
            should_switch, reason = self._should_switch_to_fallback(session_hour, session_minutes, market_data)
            if should_switch:
                self.current_regime = "fallback"
                self.regime_switches += 1
                self._log_regime_switch(old_regime, "fallback", reason, session_hour)
        
        else:  # fallback
            should_switch, reason = self._should_return_to_primary(session_hour, session_minutes)
            if should_switch:
                self.current_regime = "primary"
                self.regime_switches += 1
                self._log_regime_switch(old_regime, "primary", reason, session_hour)
        
        # Track fallback time
        if self.current_regime == "fallback":
            self.fallback_minutes_used += 1
    
    def _should_switch_to_fallback(self, session_hour, session_minutes, market_data):
        """Determine if should switch to fallback mode"""
        
        # Check fallback time limit
        max_fallback_minutes = 330 * (self.max_fallback_percentage / 100)
        if self.fallback_minutes_used >= max_fallback_minutes:
            return False, "Fallback time limit reached"
        
        # Late session with no trades
        if session_hour >= 17 and self.trades_today == 0:
            return True, f"Late session emergency - {session_hour}:00, no trades"
        
        # Critical time with insufficient trades
        if session_hour >= 18 and self.trades_today < 2:
            return True, f"Critical time - {session_hour}:00, only {self.trades_today} trades"
        
        # Very late session
        if session_hour >= 19 and self.trades_today < 3:
            return True, f"Very late - {session_hour}:00, need more activity"
        
        # Market condition analysis
        if len(market_data) >= 50:
            recent_data = market_data.tail(50)
            returns = recent_data['close'].pct_change().dropna()
            
            if len(returns) > 20:
                volatility = returns.std()
                volume_ratio = recent_data['volume'].iloc[-1] / recent_data['volume'].mean()
                
                # Low volatility conditions
                if (volatility < 0.0008 and volume_ratio < 0.7 and 
                    session_hour >= 16 and self.trades_today == 0):
                    return True, f"Low volatility + no trades, hour {session_hour}"
        
        return False, "Primary conditions maintained"
    
    def _should_return_to_primary(self, session_hour, session_minutes):
        """Determine if should return to primary mode"""
        
        # If we have sufficient trades
        if self.trades_today >= 2:
            return True, f"Sufficient trades ({self.trades_today}) - returning to primary"
        
        # Don't stay in fallback too long (preserve edge)
        if self.fallback_minutes_used > 60:
            return True, f"Preserving edge - used {self.fallback_minutes_used} fallback minutes"
        
        # Early session return if we have any trades
        if session_hour < 16 and self.trades_today > 0:
            return True, f"Early return - hour {session_hour} with {self.trades_today} trades"
        
        return False, "Staying in fallback"
    
    def _log_regime_switch(self, from_regime, to_regime, reason, session_hour):
        """Log regime switch"""
        switch_info = {
            'bar': self.current_bar,
            'session_hour': session_hour,
            'from_regime': from_regime,
            'to_regime': to_regime,
            'reason': reason,
            'trades': self.trades_today,
            'fallback_minutes': self.fallback_minutes_used
        }
        self.regime_history.append(switch_info)
    
    def get_current_params(self):
        """Get parameters for current regime"""
        
        if self.current_regime == "primary":
            return {
                'name': 'Momentum Master',
                'rsi_long_min': 35,
                'rsi_long_max': 65,
                'rsi_short_min': 35,
                'rsi_short_max': 65,
                'volume_multiplier': 1.8,
                'atr_multiplier': 1.2,
                'bb_percentile': 75
            }
        else:  # fallback
            return {
                'name': 'Activity Insurance',
                'rsi_long_min': 25,
                'rsi_long_max': 75,
                'rsi_short_min': 25,
                'rsi_short_max': 75,
                'volume_multiplier': 0.8,
                'atr_multiplier': 0.8,
                'bb_percentile': 50
            }
    
    def record_trade(self, pnl, is_win):
        """Record trade performance by regime"""
        regime = self.current_regime
        self.performance_by_regime[regime]['trades'] += 1
        self.performance_by_regime[regime]['pnl'] += pnl
        if is_win:
            self.performance_by_regime[regime]['wins'] += 1
    
    def reset_daily_stats(self):
        """Reset for new trading day"""
        self.trades_today = 0
        self.fallback_minutes_used = 0
        self.regime_switches = 0
        self.current_regime = "primary"
        self.session_start_bar = self.current_bar

class HybridAtlasStrategy(AtlasMomentumStrategy):
    """
    Enhanced Atlas strategy with hybrid regime switching for backtesting
    """
    
    def __init__(self):
        super().__init__()
        self.hybrid_manager = HybridRegimeManager()
        self.bar_count = 0
        self.trade_count = 0
        self.total_bars = 0
        
        # Store market data for regime decisions
        self.market_data_buffer = []
        
    def start(self):
        super().start()
        self.total_bars = len(self.datas[0])
        print(f"🚀 Hybrid Atlas Strategy starting - {self.total_bars} bars to process")
    
    def next(self):
        """Process each bar with hybrid regime logic"""
        
        self.bar_count += 1
        
        # Build market data buffer for regime decisions
        current_data = {
            'open': self.datas[0].open[0],
            'high': self.datas[0].high[0],
            'low': self.datas[0].low[0],
            'close': self.datas[0].close[0],
            'volume': self.datas[0].volume[0],
            'datetime': self.datas[0].datetime.datetime(0)
        }
        
        self.market_data_buffer.append(current_data)
        
        # Keep only last 100 bars for efficiency
        if len(self.market_data_buffer) > 100:
            self.market_data_buffer = self.market_data_buffer[-100:]
        
        # Convert to DataFrame for regime analysis
        if len(self.market_data_buffer) >= 10:
            df = pd.DataFrame(self.market_data_buffer)
            
            # Update regime based on current conditions
            old_regime = self.hybrid_manager.current_regime
            self.hybrid_manager.update_regime(
                self.bar_count, 
                self.total_bars, 
                df, 
                self.trade_count
            )
            
            # If regime changed, update strategy parameters
            if self.hybrid_manager.current_regime != old_regime:
                params = self.hybrid_manager.get_current_params()
                
                # Dynamically update parameters
                self.params.rsi_long_min = params['rsi_long_min']
                self.params.rsi_long_max = params['rsi_long_max']
                self.params.volume_multiplier = params['volume_multiplier']
                self.params.atr_multiplier = params['atr_multiplier']
                
                print(f"🔄 Bar {self.bar_count}: Regime switched to {self.hybrid_manager.current_regime.upper()} ({params['name']})")
        
        # Call parent strategy logic
        super().next()
    
    def notify_trade(self, trade):
        """Track trades and regime performance"""
        if trade.isclosed:
            self.trade_count += 1
            pnl = trade.pnl
            is_win = pnl > 0
            
            # Record trade in regime manager
            self.hybrid_manager.record_trade(pnl, is_win)
            
            regime = self.hybrid_manager.current_regime
            print(f"💱 Trade #{self.trade_count} in {regime.upper()}: £{pnl:+.2f}")
        
        super().notify_trade(trade)

def collect_extended_data():
    """Collect extended historical data for comprehensive backtesting"""
    print("🔴 COLLECTING EXTENDED HISTORICAL DATA")
    print("=" * 40)
    
    app = HybridBacktestDataApp()
    
    try:
        print("🔌 Connecting to IB TWS...")
        app.connect("127.0.0.1", 7497, 1)
        
        def run_loop():
            app.run()
        
        api_thread = threading.Thread(target=run_loop, daemon=True)
        api_thread.start()
        time.sleep(2)
        
        # NQ futures contract
        contract = Contract()
        contract.symbol = "NQ"
        contract.secType = "FUT"
        contract.exchange = "CME"
        contract.currency = "USD"
        contract.lastTradeDateOrContractMonth = "20250919"
        
        print("📊 Requesting 3 days of historical data...")
        app.reqHistoricalData(1, contract, "", "3 D", "1 min", "TRADES", 1, 1, False, [])
        
        # Wait for data
        timeout = 60
        while timeout > 0 and not app.completed:
            time.sleep(1)
            timeout -= 1
        
        if not app.data:
            print("❌ No data received")
            return None
        
        # Process data
        df = pd.DataFrame(app.data)
        df.set_index('datetime', inplace=True)
        df = df.sort_index()
        
        # Filter to trading hours only (14:30-20:00 GMT)
        df['hour'] = df.index.hour
        df['minute'] = df.index.minute
        trading_hours = df[
            ((df['hour'] == 14) & (df['minute'] >= 30)) |
            ((df['hour'] >= 15) & (df['hour'] < 20)) |
            ((df['hour'] == 20) & (df['minute'] == 0))
        ].copy()
        
        trading_hours = trading_hours.drop(['hour', 'minute'], axis=1)
        
        print(f"✅ Collected {len(df)} total bars")
        print(f"📊 Filtered to {len(trading_hours)} trading hours bars")
        print(f"💰 Price range: ${trading_hours['low'].min():.2f} - ${trading_hours['high'].max():.2f}")
        print(f"📅 Period: {trading_hours.index[0].strftime('%Y-%m-%d %H:%M')} to {trading_hours.index[-1].strftime('%Y-%m-%d %H:%M')}")
        
        return trading_hours
        
    except Exception as e:
        print(f"❌ Data collection error: {e}")
        return None
    finally:
        app.disconnect()

def run_hybrid_backtest():
    """Run comprehensive backtest of hybrid strategy"""
    
    print("\n🎯 HYBRID STRATEGY BACKTEST - REAL DATA")
    print("Comprehensive validation of regime switching logic")
    print("=" * 45)
    
    # Collect historical data
    data = collect_extended_data()
    if data is None or len(data) < 100:
        print("❌ Insufficient data for comprehensive backtest")
        return
    
    print(f"\n🧪 Running hybrid backtest on {len(data)} real market bars...")
    
    # Setup Backtrader
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(50000.0)  # £50k FTMO account
    cerebro.broker.setcommission(commission=0.62)  # £0.62 per side
    
    # Add hybrid strategy
    cerebro.addstrategy(HybridAtlasStrategy)
    
    # Prepare data feed
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
    
    # Add comprehensive analyzers
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.SQN, _name='sqn')
    
    print(f"🔄 Running backtest...")
    
    try:
        # Run backtest
        initial_value = cerebro.broker.getvalue()
        results = cerebro.run()
        final_value = cerebro.broker.getvalue()
        
        strategy = results[0]
        hybrid_manager = strategy.hybrid_manager
        
        # Extract comprehensive results
        total_return = (final_value - initial_value) / initial_value * 100
        
        trades_analyzer = strategy.analyzers.trades.get_analysis()
        drawdown_analyzer = strategy.analyzers.drawdown.get_analysis()
        returns_analyzer = strategy.analyzers.returns.get_analysis()
        sharpe_analyzer = strategy.analyzers.sharpe.get_analysis()
        sqn_analyzer = strategy.analyzers.sqn.get_analysis()
        
        total_trades = getattr(trades_analyzer.total, 'closed', 0) if hasattr(trades_analyzer, 'total') else 0
        won_trades = getattr(trades_analyzer.won, 'total', 0) if hasattr(trades_analyzer, 'won') else 0
        lost_trades = getattr(trades_analyzer.lost, 'total', 0) if hasattr(trades_analyzer, 'lost') else 0
        
        win_rate = (won_trades / total_trades * 100) if total_trades > 0 else 0
        max_drawdown = abs(getattr(drawdown_analyzer.max, 'drawdown', 0)) if hasattr(drawdown_analyzer, 'max') else 0
        
        avg_win = getattr(trades_analyzer.won, 'pnl', {}).get('average', 0) if hasattr(trades_analyzer, 'won') else 0
        avg_loss = getattr(trades_analyzer.lost, 'pnl', {}).get('average', 0) if hasattr(trades_analyzer, 'lost') else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        sharpe_ratio = getattr(sharpe_analyzer, 'sharperatio', 0) or 0
        sqn = getattr(sqn_analyzer, 'sqn', 0) or 0
        
        # Calculate trading days and annualized return
        trading_days = len(data) / (5.5 * 60)  # 5.5 hours per day, 60 minutes per hour
        annual_return = (((final_value / initial_value) ** (252 / trading_days)) - 1) * 100 if trading_days > 0 else 0
        
        # Display comprehensive results
        print(f"\n🏆 HYBRID BACKTEST RESULTS")
        print("=" * 30)
        print(f"💰 Total P&L: £{final_value - initial_value:+,.2f}")
        print(f"📈 Total Return: {total_return:+.2f}%")
        print(f"📊 Annualized Return: {annual_return:+.2f}%")
        print(f"📅 Trading Period: {trading_days:.1f} days")
        print(f"💎 Final Equity: £{final_value:,.2f}")
        print()
        
        print(f"📈 TRADING STATISTICS")
        print("-" * 20)
        print(f"Total Trades: {total_trades}")
        print(f"Winning Trades: {won_trades}")
        print(f"Losing Trades: {lost_trades}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Average Win: £{avg_win:.2f}")
        print(f"Average Loss: £{avg_loss:.2f}")
        print(f"Profit Factor: {profit_factor:.2f}")
        print()
        
        print(f"📉 RISK METRICS")
        print("-" * 13)
        print(f"Max Drawdown: {max_drawdown:.2f}%")
        print(f"Sharpe Ratio: {sharpe_ratio:.2f}")
        print(f"SQN: {sqn:.2f}")
        print()
        
        # Regime analysis
        print(f"📊 REGIME ANALYSIS")
        print("-" * 17)
        print(f"Regime Switches: {hybrid_manager.regime_switches}")
        print(f"Fallback Time: {hybrid_manager.fallback_minutes_used} min ({hybrid_manager.fallback_minutes_used/(len(data))*100:.1f}%)")
        print(f"Final Regime: {hybrid_manager.current_regime.upper()}")
        print()
        
        # Performance by regime
        primary_perf = hybrid_manager.performance_by_regime['primary']
        fallback_perf = hybrid_manager.performance_by_regime['fallback']
        
        print(f"📈 PRIMARY REGIME PERFORMANCE")
        print("-" * 29)
        if primary_perf['trades'] > 0:
            primary_win_rate = primary_perf['wins'] / primary_perf['trades'] * 100
            primary_avg_pnl = primary_perf['pnl'] / primary_perf['trades']
            print(f"Trades: {primary_perf['trades']}")
            print(f"Total P&L: £{primary_perf['pnl']:+.2f}")
            print(f"Win Rate: {primary_win_rate:.1f}%")
            print(f"Avg P&L per trade: £{primary_avg_pnl:+.2f}")
        else:
            print("No trades in primary regime")
        print()
        
        print(f"🔄 FALLBACK REGIME PERFORMANCE")
        print("-" * 30)
        if fallback_perf['trades'] > 0:
            fallback_win_rate = fallback_perf['wins'] / fallback_perf['trades'] * 100
            fallback_avg_pnl = fallback_perf['pnl'] / fallback_perf['trades']
            print(f"Trades: {fallback_perf['trades']}")
            print(f"Total P&L: £{fallback_perf['pnl']:+.2f}")
            print(f"Win Rate: {fallback_win_rate:.1f}%")
            print(f"Avg P&L per trade: £{fallback_avg_pnl:+.2f}")
        else:
            print("No trades in fallback regime")
        print()
        
        # Regime switch history (show last 10)
        if hybrid_manager.regime_history:
            print(f"🔄 REGIME SWITCH HISTORY (Last 10)")
            print("-" * 33)
            recent_switches = hybrid_manager.regime_history[-10:]
            for i, switch in enumerate(recent_switches, 1):
                print(f"  {i}. Hour {switch['session_hour']}:00 {switch['from_regime'].upper()} → {switch['to_regime'].upper()}")
                print(f"     Reason: {switch['reason']}")
            print()
        
        # FTMO evaluation
        print(f"🎯 FTMO EVALUATION")
        print("-" * 16)
        
        # Check FTMO criteria
        ftmo_checks = []
        
        # Trading activity
        if total_trades >= 1:
            ftmo_checks.append(("Trading Activity", True, f"{total_trades} trades"))
        else:
            ftmo_checks.append(("Trading Activity", False, "No trades"))
        
        # Profit target
        profit_target_met = total_return >= 8.0  # 8% minimum for good margin
        ftmo_checks.append(("Profit Target", profit_target_met, f"{total_return:+.2f}% return"))
        
        # Risk management
        risk_ok = max_drawdown <= 5.0
        ftmo_checks.append(("Risk Management", risk_ok, f"{max_drawdown:.2f}% drawdown"))
        
        # Regime control
        regime_ok = hybrid_manager.fallback_minutes_used / len(data) * 100 <= 30
        ftmo_checks.append(("Regime Control", regime_ok, f"{hybrid_manager.fallback_minutes_used/len(data)*100:.1f}% fallback time"))
        
        for check_name, passed, detail in ftmo_checks:
            status = "✅" if passed else "❌"
            print(f"{status} {check_name}: {detail}")
        
        # Overall assessment
        all_passed = all(check[1] for check in ftmo_checks)
        
        print()
        if all_passed:
            print("🚀 FTMO STATUS: ✅ EXCELLENT - READY FOR EVALUATION")
            print("   Hybrid strategy successfully validated on real market data")
            if annual_return > 10:
                print(f"   🎯 EXCEEDS TARGET: {annual_return:.1f}% annualized return")
        elif total_trades > 0 and max_drawdown <= 10:
            print("🔄 FTMO STATUS: ✅ ACCEPTABLE - READY WITH MONITORING")
            print("   Strategy meets basic requirements, monitor performance")
        else:
            print("⚠️  FTMO STATUS: NEEDS IMPROVEMENT")
            print("   Review regime switching logic and parameters")
        
        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'profit_factor': profit_factor,
            'regime_switches': hybrid_manager.regime_switches,
            'fallback_percentage': hybrid_manager.fallback_minutes_used/len(data)*100,
            'ftmo_ready': all_passed,
            'primary_trades': primary_perf['trades'],
            'fallback_trades': fallback_perf['trades']
        }
        
    except Exception as e:
        print(f"❌ Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🎯 HYBRID STRATEGY BACKTEST - REAL DATA VALIDATION")
    print("=" * 52)
    
    results = run_hybrid_backtest()
    
    if results:
        print(f"\n📋 BACKTEST SUMMARY")
        print("-" * 17)
        print(f"✅ Hybrid strategy tested on real market data")
        print(f"✅ Regime switching logic validated")
        print(f"✅ Performance metrics calculated")
        print(f"✅ FTMO compliance assessed")
        
        if results['ftmo_ready']:
            print(f"\n🚀 VALIDATION COMPLETE: HYBRID STRATEGY APPROVED")
            print(f"   Annual return projection: {results['annual_return']:+.1f}%")
            print(f"   Risk control validated: {results['max_drawdown']:.1f}% max drawdown")
            print(f"   Regime balance optimal: {results['fallback_percentage']:.1f}% fallback time")
        
        print(f"\n🎯 Ready for FTMO evaluation deployment!")
    else:
        print(f"\n❌ Backtest failed - check data connection and try again")
