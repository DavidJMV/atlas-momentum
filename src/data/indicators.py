"""
Technical Indicators for Atlas Trading Strategy
Custom indicators optimized for FTMO evaluation
"""

import backtrader as bt
import numpy as np
import pandas as pd
from typing import Dict, Any
from collections import deque


class TechnicalIndicators:
    """
    Collection of technical indicators for the Atlas strategy
    Optimized for momentum and volatility analysis
    """
    
    def __init__(self, data, params):
        """Initialize all technical indicators"""
        self.data = data
        self.params = params
        
        # Core Indicators
        self.atr = bt.indicators.ATR(
            data, 
            period=params.atr_period
        )
        
        self.atr_avg = bt.indicators.SMA(
            self.atr, 
            period=params.atr_lookback
        )
        
        self.ema_fast = bt.indicators.EMA(
            data.close, 
            period=params.ema_fast
        )
        
        self.ema_slow = bt.indicators.EMA(
            data.close, 
            period=params.ema_slow
        )
        
        self.rsi = bt.indicators.RSI(
            data.close, 
            period=params.rsi_period
        )
        
        self.volume_avg = bt.indicators.SMA(
            data.volume, 
            period=params.volume_period
        )
        
        # Bollinger Bands
        self.bb = bt.indicators.BollingerBands(
            data.close, 
            period=params.bb_period
        )
        self.bb_upper = self.bb.lines.top
        self.bb_lower = self.bb.lines.bot
        self.bb_mid = self.bb.lines.mid
        
        # Custom Bollinger Band Width
        self.bb_width = BollingerBandWidth(data.close, period=params.bb_period)
        self.bb_width_percentile = BollingerBandWidthPercentile(
            data.close, 
            period=params.bb_period,
            lookback=20
        )


class BollingerBandWidth(bt.Indicator):
    """
    Custom Bollinger Band Width Indicator
    Measures volatility expansion
    """
    lines = ('width',)
    params = (
        ('period', 20),
        ('devfactor', 2.0),
    )
    
    def __init__(self):
        self.bb = bt.indicators.BollingerBands(
            self.data, 
            period=self.params.period,
            devfactor=self.params.devfactor
        )
        
    def next(self):
        if len(self.bb.top) > 0 and len(self.bb.bot) > 0:
            width = (self.bb.top[0] - self.bb.bot[0]) / self.bb.mid[0] if self.bb.mid[0] != 0 else 0
            self.lines.width[0] = width
        else:
            self.lines.width[0] = 0


class BollingerBandWidthPercentile(bt.Indicator):
    """
    Bollinger Band Width Percentile Indicator
    Shows current width relative to historical distribution
    """
    lines = ('percentile',)
    params = (
        ('period', 20),
        ('lookback', 20),
        ('devfactor', 2.0),
    )
    
    def __init__(self):
        self.bb_width = BollingerBandWidth(
            self.data,
            period=self.params.period,
            devfactor=self.params.devfactor
        )
        self.width_history = deque(maxlen=self.params.lookback)
        
    def next(self):
        current_width = self.bb_width.width[0]
        
        if len(self.width_history) >= self.params.lookback:
            # Calculate percentile
            sorted_widths = sorted(self.width_history)
            rank = sum(1 for w in sorted_widths if w <= current_width)
            percentile = (rank / len(sorted_widths)) * 100
            self.lines.percentile[0] = percentile
        else:
            self.lines.percentile[0] = 50.0  # Default to median
            
        # Add current width to history
        self.width_history.append(current_width)


class VolumeProfile(bt.Indicator):
    """
    Simple Volume Profile Indicator
    Identifies high-volume price levels
    """
    lines = ('volume_ratio',)
    params = (
        ('period', 20),
    )
    
    def __init__(self):
        self.volume_avg = bt.indicators.SMA(
            self.data.volume, 
            period=self.params.period
        )
        
    def next(self):
        if self.volume_avg[0] > 0:
            self.lines.volume_ratio[0] = self.data.volume[0] / self.volume_avg[0]
        else:
            self.lines.volume_ratio[0] = 1.0


class MomentumConfirmation(bt.Indicator):
    """
    Custom Momentum Confirmation Indicator
    Combines multiple momentum signals
    """
    lines = ('momentum',)
    params = (
        ('rsi_period', 14),
        ('ema_fast', 21),
        ('ema_slow', 50),
    )
    
    def __init__(self):
        self.rsi = bt.indicators.RSI(self.data, period=self.params.rsi_period)
        self.ema_fast = bt.indicators.EMA(self.data, period=self.params.ema_fast)
        self.ema_slow = bt.indicators.EMA(self.data, period=self.params.ema_slow)
        
    def next(self):
        # Price momentum (EMA alignment)
        if self.ema_fast[0] > self.ema_slow[0]:
            ema_momentum = 1
        elif self.ema_fast[0] < self.ema_slow[0]:
            ema_momentum = -1
        else:
            ema_momentum = 0
            
        # RSI momentum
        rsi_val = self.rsi[0]
        if rsi_val > 60:
            rsi_momentum = 1
        elif rsi_val < 40:
            rsi_momentum = -1
        else:
            rsi_momentum = 0
            
        # Combined momentum score
        momentum_score = (ema_momentum + rsi_momentum) / 2
        self.lines.momentum[0] = momentum_score


class VolatilityRegime(bt.Indicator):
    """
    Volatility Regime Indicator
    Identifies high/low volatility periods
    """
    lines = ('regime',)
    params = (
        ('atr_period', 14),
        ('atr_lookback', 50),
        ('threshold', 1.2),
    )
    
    def __init__(self):
        self.atr = bt.indicators.ATR(self.data, period=self.params.atr_period)
        self.atr_avg = bt.indicators.SMA(self.atr, period=self.params.atr_lookback)
        
    def next(self):
        if self.atr_avg[0] > 0:
            vol_ratio = self.atr[0] / self.atr_avg[0]
            if vol_ratio > self.params.threshold:
                self.lines.regime[0] = 1  # High volatility
            else:
                self.lines.regime[0] = 0  # Normal/Low volatility
        else:
            self.lines.regime[0] = 0


class TrendStrength(bt.Indicator):
    """
    Trend Strength Indicator
    Measures the strength of the current trend
    """
    lines = ('strength',)
    params = (
        ('ema_fast', 21),
        ('ema_slow', 50),
        ('atr_period', 14),
    )
    
    def __init__(self):
        self.ema_fast = bt.indicators.EMA(self.data, period=self.params.ema_fast)
        self.ema_slow = bt.indicators.EMA(self.data, period=self.params.ema_slow)
        self.atr = bt.indicators.ATR(self.data, period=self.params.atr_period)
        
    def next(self):
        if self.atr[0] > 0:
            ema_diff = abs(self.ema_fast[0] - self.ema_slow[0])
            trend_strength = ema_diff / self.atr[0]
            self.lines.strength[0] = min(trend_strength, 5.0)  # Cap at 5.0
        else:
            self.lines.strength[0] = 0.0


class MarketSession(bt.Indicator):
    """
    Market Session Indicator
    Identifies different trading sessions
    """
    lines = ('session',)
    
    def next(self):
        current_time = self.data.datetime.datetime(0).time()
        hour = current_time.hour
        
        # GMT hours
        if 8 <= hour < 16:
            self.lines.session[0] = 1  # London session
        elif 14 <= hour < 21:
            self.lines.session[0] = 2  # US overlap/session
        else:
            self.lines.session[0] = 0  # Off-hours
