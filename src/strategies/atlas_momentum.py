"""
Atlas Momentum Breakout Strategy
Core strategy implementation for FTMO evaluation
"""

import backtrader as bt
import numpy as np
import pandas as pd
from typing import Optional, Dict, Any, List
from datetime import datetime, time
import ta  # Technical Analysis library
from dataclasses import dataclass

from ..risk_management.position_sizer import FTMOPositionSizer
from ..risk_management.risk_manager import FTMORiskManager
from ..data.indicators import TechnicalIndicators
from config.config import config


@dataclass
class TradeSignal:
    """Trade signal data structure"""
    timestamp: datetime
    signal_type: str  # "LONG", "SHORT", "CLOSE"
    confidence: float  # 0.0 to 1.0
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float
    metadata: Dict[str, Any]


class AtlasMomentumStrategy(bt.Strategy):
    """
    Atlas Momentum Breakout Strategy for FTMO Evaluation
    
    Core Logic:
    - Momentum + Volatility breakout on NQ 1-minute data
    - Strict FTMO-compliant risk management
    - Adaptive position sizing and trade management
    """
    
    params = (
        # Technical Indicator Parameters
        ('atr_period', config.trading.atr_period),
        ('atr_lookback', config.trading.atr_lookback),
        ('atr_multiplier', config.trading.atr_multiplier),
        ('ema_fast', config.trading.ema_fast),
        ('ema_slow', config.trading.ema_slow),
        ('rsi_period', config.trading.rsi_period),
        ('rsi_long_min', config.trading.rsi_long_min),
        ('rsi_long_max', config.trading.rsi_long_max),
        ('rsi_short_min', config.trading.rsi_short_min),
        ('rsi_short_max', config.trading.rsi_short_max),
        ('volume_multiplier', config.trading.volume_multiplier),
        ('volume_period', config.trading.volume_period),
        ('bb_period', config.trading.bb_period),
        ('bb_percentile', config.trading.bb_percentile),
        
        # Risk Management Parameters
        ('stop_loss_atr_mult', config.trading.stop_loss_atr_mult),
        ('reward_risk_ratio', config.trading.reward_risk_ratio),
        ('trailing_stop_atr_mult', config.trading.trailing_stop_atr_mult),
        ('trailing_activation_mult', config.trading.trailing_activation_mult),
        
        # Trading Session Parameters
        ('session_start_hour', 14),
        ('session_start_minute', 30),
        ('session_end_hour', 20),
        ('session_end_minute', 0),
        ('close_before_end_minutes', config.trading.close_before_end_minutes),
        
        # Trade Management
        ('max_trades_per_day', config.trading.max_trades_per_day),
        ('min_gap_between_trades', config.trading.min_gap_between_trades_minutes),
        ('avoid_first_last_minutes', config.trading.avoid_first_last_minutes),
    )
    
    def __init__(self):
        """Initialize strategy with indicators and risk management"""
        
        # Data feeds
        self.data_close = self.data.close
        self.data_high = self.data.high
        self.data_low = self.data.low
        self.data_volume = self.data.volume
        
        # Technical Indicators
        self.indicators = TechnicalIndicators(self.data, self.params)
        
        # Risk Management Components
        self.risk_manager = FTMORiskManager()
        self.position_sizer = FTMOPositionSizer()
        
        # Strategy State
        self.trades_today = 0
        self.last_trade_time = None
        self.daily_pnl = 0.0
        self.peak_equity = config.ftmo.account_size
        self.current_drawdown = 0.0
        self.realized_pnl = 0.0
        
        # Trade Management
        self.current_stop_loss = None
        self.current_take_profit = None
        self.trailing_stop_active = False
        self.entry_price = None
        
        # Performance Tracking
        self.trade_log = []
        self.daily_stats = []
        
    def next(self):
        """Main strategy logic called on each bar"""
        
        if len(self.data) < max(self.params.ema_slow, self.params.bb_period):
            return  # Not enough data for indicators
            
        # Update strategy state
        self._update_state()
        
        # Check if we should close positions due to time or risk limits
        if self._should_close_positions():
            self._close_all_positions("TIME_EXIT")
            return
            
        # Check for trade opportunities
        if self.position.size == 0:  # No open positions
            signal = self._generate_signal()
            if signal and self._can_open_trade():
                self._execute_entry(signal)
        else:  # Manage existing position
            self._manage_position()
    
    def _update_state(self):
        """Update strategy state variables"""
        current_time = self.data.datetime.datetime(0)
        
        # Reset daily counters at session start
        if (current_time.hour == self.params.session_start_hour and 
            current_time.minute == self.params.session_start_minute):
            self.trades_today = 0
            self.daily_pnl = 0.0
            
        # Update equity and drawdown
        current_equity = self.broker.getvalue()
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
            
        self.current_drawdown = (self.peak_equity - current_equity) / config.ftmo.account_size
    
    def _should_close_positions(self) -> bool:
        """Check if positions should be closed due to time or risk constraints"""
        current_time = self.data.datetime.datetime(0)
        
        # Close before session end
        session_end = time(self.params.session_end_hour, self.params.session_end_minute)
        close_time = time(
            session_end.hour,
            max(0, session_end.minute - self.params.close_before_end_minutes)
        )
        
        if current_time.time() >= close_time:
            return True
            
        # Risk-based exits
        if self.daily_pnl <= -config.ftmo.max_daily_loss:
            return True
            
        if self.current_drawdown >= config.ftmo.max_total_loss_pct:
            return True
            
        return False
    
    def _generate_signal(self) -> Optional[TradeSignal]:
        """Generate trading signal based on strategy conditions"""
        
        if not self._is_trading_session():
            return None
            
        # Get current indicator values
        indicators = self._get_current_indicators()
        
        # Check volatility expansion condition
        if not self._volatility_expansion(indicators):
            return None
            
        # Check volume condition
        if not self._volume_confirmation(indicators):
            return None
            
        # Check Bollinger Band width
        if not self._bollinger_width_condition(indicators):
            return None
            
        # Generate LONG signal
        long_signal = self._check_long_conditions(indicators)
        if long_signal:
            return self._create_long_signal(indicators)
            
        # Generate SHORT signal  
        short_signal = self._check_short_conditions(indicators)
        if short_signal:
            return self._create_short_signal(indicators)
            
        return None
    
    def _is_trading_session(self) -> bool:
        """Check if current time is within trading session"""
        from datetime import datetime, time, timedelta
        
        current_time = self.data.datetime.datetime(0).time()
        session_start = time(self.params.session_start_hour, self.params.session_start_minute)
        session_end = time(self.params.session_end_hour, self.params.session_end_minute)
        
        # Create datetime objects for proper time arithmetic
        today = datetime.now().date()
        session_start_dt = datetime.combine(today, session_start)
        session_end_dt = datetime.combine(today, session_end)
        
        # Add buffer to avoid trading at session boundaries
        buffer_start_dt = session_start_dt + timedelta(minutes=self.params.avoid_first_last_minutes)
        buffer_end_dt = session_end_dt - timedelta(minutes=self.params.avoid_first_last_minutes)
        
        # Convert back to time objects
        buffer_start = buffer_start_dt.time()
        buffer_end = buffer_end_dt.time()
        
        return buffer_start <= current_time <= buffer_end
    
    def _get_current_indicators(self) -> Dict[str, float]:
        """Get current values of all technical indicators"""
        return {
            'atr_current': self.indicators.atr[0],
            'atr_avg': self.indicators.atr_avg[0],
            'ema_fast': self.indicators.ema_fast[0],
            'ema_slow': self.indicators.ema_slow[0],
            'rsi': self.indicators.rsi[0],
            'volume_avg': self.indicators.volume_avg[0],
            'bb_upper': self.indicators.bb_upper[0],
            'bb_lower': self.indicators.bb_lower[0],
            'bb_width': self.indicators.bb_width[0],
            'bb_width_percentile': self.indicators.bb_width_percentile[0],
            'price': self.data_close[0],
            'volume': self.data_volume[0]
        }
    
    def _volatility_expansion(self, indicators: Dict[str, float]) -> bool:
        """Check volatility expansion condition"""
        return indicators['atr_current'] > (self.params.atr_multiplier * indicators['atr_avg'])
    
    def _volume_confirmation(self, indicators: Dict[str, float]) -> bool:
        """Check volume confirmation condition"""
        return indicators['volume'] > (self.params.volume_multiplier * indicators['volume_avg'])
    
    def _bollinger_width_condition(self, indicators: Dict[str, float]) -> bool:
        """Check Bollinger Band width condition"""
        return indicators['bb_width_percentile'] > self.params.bb_percentile
    
    def _check_long_conditions(self, indicators: Dict[str, float]) -> bool:
        """Check all conditions for LONG signal"""
        return (
            indicators['price'] > indicators['ema_fast'] and
            indicators['ema_fast'] > indicators['ema_slow'] and
            self.params.rsi_long_min <= indicators['rsi'] <= self.params.rsi_long_max
        )
    
    def _check_short_conditions(self, indicators: Dict[str, float]) -> bool:
        """Check all conditions for SHORT signal"""
        return (
            indicators['price'] < indicators['ema_fast'] and
            indicators['ema_fast'] < indicators['ema_slow'] and
            self.params.rsi_short_min <= indicators['rsi'] <= self.params.rsi_short_max
        )
    
    def _create_long_signal(self, indicators: Dict[str, float]) -> TradeSignal:
        """Create LONG trade signal with risk management levels"""
        entry_price = indicators['price']
        stop_distance = min(
            self.params.stop_loss_atr_mult * indicators['atr_current'],
            config.ftmo.max_trade_risk / config.trading.initial_position_size
        )
        
        stop_loss = entry_price - stop_distance
        take_profit = entry_price + (stop_distance * self.params.reward_risk_ratio)
        
        return TradeSignal(
            timestamp=self.data.datetime.datetime(0),
            signal_type="LONG",
            confidence=self._calculate_signal_confidence(indicators, "LONG"),
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=self.params.reward_risk_ratio,
            metadata=indicators.copy()
        )
    
    def _create_short_signal(self, indicators: Dict[str, float]) -> TradeSignal:
        """Create SHORT trade signal with risk management levels"""
        entry_price = indicators['price']
        stop_distance = min(
            self.params.stop_loss_atr_mult * indicators['atr_current'],
            config.ftmo.max_trade_risk / config.trading.initial_position_size
        )
        
        stop_loss = entry_price + stop_distance
        take_profit = entry_price - (stop_distance * self.params.reward_risk_ratio)
        
        return TradeSignal(
            timestamp=self.data.datetime.datetime(0),
            signal_type="SHORT",
            confidence=self._calculate_signal_confidence(indicators, "SHORT"),
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=self.params.reward_risk_ratio,
            metadata=indicators.copy()
        )
    
    def _calculate_signal_confidence(self, indicators: Dict[str, float], signal_type: str) -> float:
        """Calculate signal confidence based on indicator strength"""
        confidence = 0.5  # Base confidence
        
        # Volatility boost
        vol_ratio = indicators['atr_current'] / indicators['atr_avg']
        confidence += min(0.2, (vol_ratio - 1.0) * 0.4)
        
        # Volume boost
        vol_ratio = indicators['volume'] / indicators['volume_avg']
        confidence += min(0.1, (vol_ratio - 1.0) * 0.2)
        
        # Trend strength boost
        if signal_type == "LONG":
            trend_strength = (indicators['ema_fast'] - indicators['ema_slow']) / indicators['atr_current']
        else:
            trend_strength = (indicators['ema_slow'] - indicators['ema_fast']) / indicators['atr_current']
            
        confidence += min(0.2, max(0, trend_strength * 0.1))
        
        return min(1.0, max(0.0, confidence))
    
    def _can_open_trade(self) -> bool:
        """Check if we can open a new trade"""
        current_time = self.data.datetime.datetime(0)
        
        # Check trade limits
        if self.trades_today >= self.params.max_trades_per_day:
            return False
            
        # Check gap between trades
        if (self.last_trade_time and 
            (current_time - self.last_trade_time).total_seconds() < 
            self.params.min_gap_between_trades * 60):
            return False
            
        # Check risk limits
        if not self.risk_manager.can_open_trade(self.daily_pnl, self.current_drawdown):
            return False
            
        return True
    
    def _execute_entry(self, signal: TradeSignal):
        """Execute trade entry based on signal"""
        
        # Calculate position size
        position_size = self.position_sizer.calculate_size(
            signal.entry_price,
            signal.stop_loss,
            self.broker.getvalue(),
            self.realized_pnl,
            self.current_drawdown
        )
        
        if position_size == 0:
            return
            
        # Execute order
        if signal.signal_type == "LONG":
            order = self.buy(size=position_size)
        else:
            order = self.sell(size=position_size)
            
        # Set trade management variables
        self.entry_price = signal.entry_price
        self.current_stop_loss = signal.stop_loss
        self.current_take_profit = signal.take_profit
        self.trailing_stop_active = False
        
        # Update counters
        self.trades_today += 1
        self.last_trade_time = signal.timestamp
        
        # Log trade
        self.trade_log.append({
            'timestamp': signal.timestamp,
            'signal': signal.signal_type,
            'entry_price': signal.entry_price,
            'stop_loss': signal.stop_loss,
            'take_profit': signal.take_profit,
            'confidence': signal.confidence,
            'position_size': position_size
        })
    
    def _manage_position(self):
        """Manage existing position with stops and targets"""
        
        if self.position.size == 0:
            return
            
        current_price = self.data_close[0]
        position_pnl = self.position.size * (current_price - self.entry_price)
        
        # Check stop loss
        if ((self.position.size > 0 and current_price <= self.current_stop_loss) or
            (self.position.size < 0 and current_price >= self.current_stop_loss)):
            self._close_all_positions("STOP_LOSS")
            return
            
        # Check take profit
        if ((self.position.size > 0 and current_price >= self.current_take_profit) or
            (self.position.size < 0 and current_price <= self.current_take_profit)):
            self._close_all_positions("TAKE_PROFIT")
            return
            
        # Activate trailing stop
        initial_risk = abs(self.entry_price - self.current_stop_loss)
        if not self.trailing_stop_active and abs(position_pnl) >= (initial_risk * self.params.trailing_activation_mult):
            self.trailing_stop_active = True
            
        # Update trailing stop
        if self.trailing_stop_active:
            self._update_trailing_stop(current_price)
    
    def _update_trailing_stop(self, current_price: float):
        """Update trailing stop loss"""
        indicators = self._get_current_indicators()
        trail_distance = self.params.trailing_stop_atr_mult * indicators['atr_current']
        
        if self.position.size > 0:  # Long position
            new_stop = current_price - trail_distance
            if new_stop > self.current_stop_loss:
                self.current_stop_loss = new_stop
        else:  # Short position
            new_stop = current_price + trail_distance
            if new_stop < self.current_stop_loss:
                self.current_stop_loss = new_stop
    
    def _close_all_positions(self, reason: str):
        """Close all open positions"""
        if self.position.size != 0:
            self.close()
            
            # Log exit
            exit_price = self.data_close[0]
            pnl = self.position.size * (exit_price - self.entry_price)
            self.daily_pnl += pnl
            self.realized_pnl += pnl
            
            self.trade_log[-1].update({
                'exit_time': self.data.datetime.datetime(0),
                'exit_price': exit_price,
                'exit_reason': reason,
                'pnl': pnl
            })
            
        # Reset trade management variables
        self.entry_price = None
        self.current_stop_loss = None
        self.current_take_profit = None
        self.trailing_stop_active = False
    
    def stop(self):
        """Called when strategy stops - final cleanup and reporting"""
        
        # Calculate final statistics
        total_trades = len([t for t in self.trade_log if 'pnl' in t])
        winning_trades = len([t for t in self.trade_log if t.get('pnl', 0) > 0])
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        total_pnl = sum(t.get('pnl', 0) for t in self.trade_log)
        
        print(f"Strategy Performance Summary:")
        print(f"Total Trades: {total_trades}")
        print(f"Win Rate: {win_rate:.2%}")
        print(f"Total P/L: £{total_pnl:.2f}")
        print(f"Final Equity: £{self.broker.getvalue():.2f}")
        print(f"Max Drawdown: {self.current_drawdown:.2%}")
