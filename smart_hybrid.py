#!/usr/bin/env python3
"""
Enhanced FTMO Hybrid Strategy - Production Implementation
Intelligent regime switching between proven parameters and activity-ensuring fallback
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

class HybridDataApp(EWrapper, EClient):
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

class IntelligentHybridStrategy:
    """
    Intelligent FTMO Hybrid Strategy
    
    Maintains 11.52% proven edge while ensuring FTMO activity through:
    1. Primary: Strict parameters (80% time max)
    2. Fallback: Moderate parameters (20% emergency use)
    3. Smart switching based on market conditions and time
    """
    
    def __init__(self):
        self.current_regime = "primary"
        self.regime_switch_count = 0
        self.moderate_time_minutes = 0
        self.session_start_time = None
        self.daily_trades = 0
        self.last_regime_switch = None
        self.session_minutes_elapsed = 0
        
        # Regime tracking
        self.regime_history = []
        
        # Enhanced configuration
        self.max_moderate_percentage = 25  # Up to 25% time in moderate mode
        self.max_switches_per_day = 3      # Allow more switching
        self.switch_cooldown_minutes = 20  # Shorter cooldown
        self.activity_urgency_time = 17    # Hour when activity becomes urgent
        
    def simulate_session_time(self, current_bar_index, total_bars):
        """Simulate session time progression for testing"""
        # Map bars to session time (14:30-20:00 = 330 minutes)
        session_progress = current_bar_index / total_bars
        session_minutes = int(session_progress * 330)
        
        # Convert to actual hour (14:30 + minutes)
        start_hour = 14
        start_minute = 30
        
        total_minutes = start_hour * 60 + start_minute + session_minutes
        current_hour = total_minutes // 60
        current_minute = total_minutes % 60
        
        return current_hour, current_minute
    
    def should_switch_to_fallback(self, market_data, current_bar_index, total_bars):
        """Enhanced switching logic for fallback mode"""
        
        current_hour, current_minute = self.simulate_session_time(current_bar_index, total_bars)
        session_progress = current_bar_index / total_bars
        
        # Safety checks
        if self.regime_switch_count >= self.max_switches_per_day:
            return False, "Maximum switches reached"
        
        # Moderate time limit check
        max_moderate_minutes = 330 * (self.max_moderate_percentage / 100)  # 25% of 330 min
        if self.moderate_time_minutes >= max_moderate_minutes:
            return False, "Moderate time limit reached"
        
        # PRIMARY SWITCHING CONDITIONS
        
        # 1. Late session emergency (after 17:00 with no trades)
        if current_hour >= 17 and self.daily_trades == 0:
            return True, f"Late session emergency - Hour {current_hour}:00, no trades"
        
        # 2. Very late session (after 18:30 with insufficient trades)
        if current_hour >= 18 and current_minute >= 30 and self.daily_trades < 2:
            return True, f"Very late session - Hour {current_hour}:{current_minute:02d}, only {self.daily_trades} trades"
        
        # 3. Critical session end (after 19:00 with < 3 trades)
        if current_hour >= 19 and self.daily_trades < 3:
            return True, f"Critical session end - Hour {current_hour}:00, insufficient trades"
        
        # 4. Market condition analysis (if sufficient data)
        if len(market_data) >= 50:
            recent_data = market_data.tail(50)
            
            # Volatility analysis
            returns = recent_data['close'].pct_change().dropna()
            if len(returns) > 0:
                current_vol = returns.std() * np.sqrt(1440)  # Annualized volatility
                
                # ATR analysis for trend strength
                if len(recent_data) >= 14:
                    high = recent_data['high']
                    low = recent_data['low']
                    close = recent_data['close']
                    
                    # Calculate True Range
                    tr1 = high - low
                    tr2 = abs(high - close.shift(1))
                    tr3 = abs(low - close.shift(1))
                    
                    tr_df = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3})
                    true_range = tr_df.max(axis=1)
                    atr = true_range.rolling(window=14).mean()
                    
                    if len(atr) > 14 and not atr.empty:
                        atr_current = atr.iloc[-1]
                        atr_mean = atr.mean()
                        atr_ratio = atr_current / atr_mean if atr_mean > 0 else 1.0
                        
                        # Volume analysis
                        volume_ma = recent_data['volume'].rolling(window=20).mean()
                        volume_current = recent_data['volume'].iloc[-1]
                        volume_mean = volume_ma.iloc[-1]
                        volume_ratio = volume_current / volume_mean if volume_mean > 0 else 1.0
                        
                        # Low volatility + low volume conditions
                        if (atr_ratio < 0.7 and volume_ratio < 0.8 and 
                            current_vol < 0.010 and current_hour >= 16):
                            return True, f"Low volatility conditions (ATR: {atr_ratio:.2f}, Vol: {volume_ratio:.2f}, Session: {current_hour}:00)"
        
        # 5. Extended period without switching (progressive urgency)
        bars_since_start = current_bar_index
        if bars_since_start > 180 and self.daily_trades == 0:  # 3+ hours with no trades
            return True, f"Extended period without activity - {bars_since_start} bars, no trades"
        
        return False, "Primary conditions maintained"
    
    def should_switch_to_primary(self, market_data, current_bar_index, total_bars):
        """Logic for switching back to primary"""
        
        current_hour, current_minute = self.simulate_session_time(current_bar_index, total_bars)
        
        # 1. If we have sufficient trades, consider switching back
        if self.daily_trades >= 2:
            return True, f"Sufficient trades achieved ({self.daily_trades}) - returning to primary"
        
        # 2. If volatility has improved significantly
        if len(market_data) >= 30:
            recent_data = market_data.tail(30)
            returns = recent_data['close'].pct_change().dropna()
            
            if len(returns) > 0:
                current_vol = returns.std() * np.sqrt(1440)
                
                # If volatility is good, switch back
                if current_vol > 0.015:
                    return True, f"Volatility improved ({current_vol:.4f}) - returning to primary"
        
        # 3. Don't stay in fallback too long (preserve edge)
        if self.moderate_time_minutes > 60:  # After 1 hour in moderate
            return True, f"Extended moderate time ({self.moderate_time_minutes} min) - preserving edge"
        
        # 4. Early session return (before 16:00 if we have any trades)
        if current_hour < 16 and self.daily_trades > 0:
            return True, f"Early session return - Hour {current_hour}:00 with {self.daily_trades} trades"
        
        return False, "Fallback conditions maintained"
    
    def update_regime(self, market_data, current_bar_index, total_bars):
        """Update regime based on current conditions"""
        
        self.session_minutes_elapsed = int((current_bar_index / total_bars) * 330)
        
        if self.current_regime == "primary":
            should_switch, reason = self.should_switch_to_fallback(market_data, current_bar_index, total_bars)
            if should_switch:
                self._execute_regime_switch("fallback", reason)
        else:  # fallback
            should_switch, reason = self.should_switch_to_primary(market_data, current_bar_index, total_bars)
            if should_switch:
                self._execute_regime_switch("primary", reason)
        
        # Update moderate time tracking
        if self.current_regime == "fallback":
            self.moderate_time_minutes += 1  # 1 minute per bar
    
    def _execute_regime_switch(self, new_regime, reason):
        """Execute the regime switch"""
        
        old_regime = self.current_regime
        self.current_regime = new_regime
        self.regime_switch_count += 1
        self.last_regime_switch = datetime.now()
        
        switch_info = {
            'timestamp': datetime.now(),
            'from_regime': old_regime,
            'to_regime': new_regime,
            'reason': reason,
            'daily_trades': self.daily_trades,
            'moderate_time': self.moderate_time_minutes,
            'session_minutes': self.session_minutes_elapsed
        }
        
        self.regime_history.append(switch_info)
        
        print(f"🔄 REGIME SWITCH: {old_regime.upper()} → {new_regime.upper()}")
        print(f"   Reason: {reason}")
        print(f"   Trades: {self.daily_trades}, Moderate time: {self.moderate_time_minutes} min")
    
    def get_config_for_regime(self, regime):
        """Get configuration for specified regime"""
        
        if regime == "primary":
            # Original Momentum Master parameters (11.52% proven)
            return {
                'regime': 'primary',
                'description': 'Momentum Master - Original 11.52% parameters',
                'rsi_long_min': 35,
                'rsi_long_max': 65,
                'rsi_short_min': 35,
                'rsi_short_max': 65,
                'rsi_period': 12,
                'volume_multiplier': 1.8,
                'volume_period': 25,
                'atr_multiplier': 1.2,
                'bb_percentile': 75,
                'atr_period': 16,
                'ema_fast': 15,
                'ema_slow': 35,
                'stop_loss_atr_mult': 2.5,
                'reward_risk_ratio': 3.0
            }
        else:  # fallback
            # Moderate parameters for activity insurance
            return {
                'regime': 'fallback',
                'description': 'Activity Insurance - Moderate parameters',
                'rsi_long_min': 30,
                'rsi_long_max': 70,
                'rsi_short_min': 30,
                'rsi_short_max': 70,
                'rsi_period': 12,
                'volume_multiplier': 1.0,
                'volume_period': 25,
                'atr_multiplier': 0.9,
                'bb_percentile': 55,
                'atr_period': 16,
                'ema_fast': 15,
                'ema_slow': 35,
                'stop_loss_atr_mult': 2.5,
                'reward_risk_ratio': 3.0
            }
    
    def register_trade(self):
        """Register a new trade"""
        self.daily_trades += 1
        print(f"📈 Trade #{self.daily_trades} executed in {self.current_regime.upper()} regime")

def collect_live_data():
    """Collect live NQ data"""
    print("🔴 COLLECTING LIVE NQ DATA")
    print("=" * 28)
    
    app = HybridDataApp()
    
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
        
        print("📊 Requesting live NQ data...")
        app.reqHistoricalData(1, contract, "", "1 D", "1 min", "TRADES", 1, 1, False, [])
        
        timeout = 30
        while timeout > 0 and not app.completed:
            time.sleep(1)
            timeout -= 1
        
        if not app.data:
            print("❌ No data received")
            return None
        
        df = pd.DataFrame(app.data)
        df.set_index('datetime', inplace=True)
        df = df.sort_index()
        
        print(f"✅ Got {len(df)} live bars")
        print(f"💰 Current NQ: ${df['close'].iloc[-1]:.2f}")
        
        return df
        
    except Exception as e:
        print(f"❌ Error collecting data: {e}")
        return None
    finally:
        app.disconnect()

class HybridAtlasStrategy(AtlasMomentumStrategy):
    """Extended Atlas strategy with hybrid regime switching"""
    
    def __init__(self):
        super().__init__()
        self.hybrid_manager = IntelligentHybridStrategy()
        self.bar_count = 0
        self.total_bars = 0
        
    def start(self):
        """Initialize strategy"""
        super().start()
        print("🚀 Hybrid Atlas Strategy initialized")
        self.total_bars = len(self.datas[0])
        print(f"📊 Total bars to process: {self.total_bars}")
    
    def next(self):
        """Process each bar with regime switching"""
        
        self.bar_count += 1
        
        # Get current data as DataFrame for analysis
        data_dict = {
            'open': [self.datas[0].open[i] for i in range(-min(100, len(self.datas[0])), 1)],
            'high': [self.datas[0].high[i] for i in range(-min(100, len(self.datas[0])), 1)],
            'low': [self.datas[0].low[i] for i in range(-min(100, len(self.datas[0])), 1)],
            'close': [self.datas[0].close[i] for i in range(-min(100, len(self.datas[0])), 1)],
            'volume': [self.datas[0].volume[i] for i in range(-min(100, len(self.datas[0])), 1)]
        }
        
        current_data = pd.DataFrame(data_dict)
        
        # Update regime based on current conditions
        old_regime = self.hybrid_manager.current_regime
        self.hybrid_manager.update_regime(current_data, self.bar_count, self.total_bars)
        
        # If regime changed, update parameters
        if self.hybrid_manager.current_regime != old_regime:
            config = self.hybrid_manager.get_config_for_regime(self.hybrid_manager.current_regime)
            # Update strategy parameters dynamically
            self.params.volume_multiplier = config['volume_multiplier']
            self.params.atr_multiplier = config['atr_multiplier']
            self.params.rsi_long_min = config['rsi_long_min']
            self.params.rsi_long_max = config['rsi_long_max']
        
        # Call parent strategy logic
        super().next()
    
    def notify_trade(self, trade):
        """Track trades for regime decisions"""
        if trade.isclosed:
            self.hybrid_manager.register_trade()
        super().notify_trade(trade)

def run_hybrid_strategy():
    """Run the intelligent hybrid strategy"""
    
    print("🎯 INTELLIGENT FTMO HYBRID STRATEGY")
    print("Balancing proven edge with activity insurance")
    print("=" * 45)
    
    # Get live data
    df = collect_live_data()
    if df is None or len(df) < 20:
        print("❌ Insufficient data for strategy test")
        return
    
    print(f"\n🧪 Testing on {len(df)} live CME bars...")
    
    # Setup Backtrader
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(50000.0)  # £50k FTMO
    cerebro.broker.setcommission(commission=0.62)
    
    # Add hybrid strategy
    cerebro.addstrategy(HybridAtlasStrategy)
    
    # Prepare data
    df_formatted = df.copy()
    df_formatted.columns = ['open', 'high', 'low', 'close', 'volume']
    
    # Create data feed
    class LivePandasData(bt.feeds.PandasData):
        params = (
            ('datetime', None),
            ('open', 'open'),
            ('high', 'high'),
            ('low', 'low'),
            ('close', 'close'),
            ('volume', 'volume'),
            ('openinterest', None),
        )
    
    data_feed = LivePandasData(dataname=df_formatted)
    cerebro.adddata(data_feed)
    
    # Add analyzers
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    
    print(f"🔄 Running intelligent hybrid strategy...")
    
    try:
        initial_value = cerebro.broker.getvalue()
        results = cerebro.run()
        final_value = cerebro.broker.getvalue()
        
        strategy = results[0]
        hybrid_manager = strategy.hybrid_manager
        
        # Extract results
        total_return = (final_value - initial_value) / initial_value * 100
        
        trades_analyzer = strategy.analyzers.trades.get_analysis()
        drawdown_analyzer = strategy.analyzers.drawdown.get_analysis()
        
        total_trades = getattr(trades_analyzer.total, 'closed', 0) if hasattr(trades_analyzer, 'total') else 0
        won_trades = getattr(trades_analyzer.won, 'total', 0) if hasattr(trades_analyzer, 'won') else 0
        win_rate = (won_trades / total_trades * 100) if total_trades > 0 else 0
        max_drawdown = abs(getattr(drawdown_analyzer.max, 'drawdown', 0)) if hasattr(drawdown_analyzer, 'max') else 0
        
        # Results
        print(f"\n🏆 HYBRID STRATEGY RESULTS")
        print("=" * 30)
        print(f"💰 P&L: £{final_value - initial_value:.2f} ({total_return:+.2f}%)")
        print(f"📊 Data: {len(df)} live CME bars")
        print(f"📈 Trades: {total_trades}")
        print(f"🎯 Win Rate: {win_rate:.1f}%")
        print(f"📉 Max Drawdown: {max_drawdown:.2f}%")
        
        # Regime analysis
        print(f"\n📊 REGIME PERFORMANCE")
        print("-" * 22)
        print(f"Final Regime: {hybrid_manager.current_regime.upper()}")
        print(f"Regime Switches: {hybrid_manager.regime_switch_count}")
        print(f"Moderate Time: {hybrid_manager.moderate_time_minutes} min ({hybrid_manager.moderate_time_minutes/330*100:.1f}%)")
        print(f"Daily Trades: {hybrid_manager.daily_trades}")
        
        if hybrid_manager.regime_history:
            print(f"\n🔄 Regime Switch History:")
            for i, switch in enumerate(hybrid_manager.regime_history, 1):
                time_str = f"{switch['session_minutes']//60}:{switch['session_minutes']%60:02d}"
                print(f"  {i}. {time_str} {switch['from_regime'].upper()} → {switch['to_regime'].upper()}")
                print(f"     Reason: {switch['reason']}")
        
        # FTMO evaluation
        print(f"\n🎯 FTMO READINESS")
        print("-" * 16)
        
        session_hours = len(df) / 60
        
        if total_trades > 0:
            print(f"✅ Trading Activity: {total_trades} trades in {session_hours:.1f}h")
            if max_drawdown <= 3.0:
                print(f"✅ Risk Control: {max_drawdown:.2f}% drawdown")
            else:
                print(f"⚠️  Risk Warning: {max_drawdown:.2f}% drawdown")
                
            print(f"✅ Regime Control: {hybrid_manager.moderate_time_minutes/330*100:.1f}% moderate time")
            
            if total_return >= 0 and max_drawdown <= 5.0:
                print(f"\n🚀 STATUS: ✅ READY FOR FTMO EVALUATION")
                print(f"   Hybrid approach successfully proven")
            else:
                print(f"\n⚠️  STATUS: NEEDS FINE-TUNING")
        else:
            print(f"❌ No trades - fallback activation needed")
        
        return total_return, total_trades, max_drawdown
        
    except Exception as e:
        print(f"❌ Strategy execution failed: {e}")
        return None, 0, 0

if __name__ == "__main__":
    run_hybrid_strategy()
