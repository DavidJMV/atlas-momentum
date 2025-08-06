#!/usr/bin/env python3
"""
Adaptive Atlas Strategy Configuration
Switches between high-volatility and moderate-volatility parameters
based on real-time market regime detection
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

import numpy as np
import pandas as pd
from typing import Dict, Literal

def detect_market_regime(data: pd.DataFrame, lookback: int = 50) -> Literal["high_vol", "moderate_vol"]:
    """
    Detect current market volatility regime
    
    Returns:
        "high_vol": Use original strict parameters (11.52% backtested)
        "moderate_vol": Use relaxed parameters (live tested +3.01%)
    """
    
    if len(data) < lookback:
        return "moderate_vol"  # Default to safer parameters
    
    # Calculate volatility metrics
    recent_data = data.tail(lookback)
    
    # ATR-based volatility measure
    high = recent_data['high']
    low = recent_data['low'] 
    close = recent_data['close']
    
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=14).mean()
    
    current_atr = atr.iloc[-1]
    avg_atr = atr.mean()
    atr_ratio = current_atr / avg_atr
    
    # Volume surge detection
    volume = recent_data['volume']
    volume_ma = volume.rolling(window=20).mean()
    volume_ratio = (volume / volume_ma).mean()
    
    # Bollinger Band width
    bb_middle = close.rolling(window=20).mean()
    bb_std = close.rolling(window=20).std()
    bb_width = (bb_std * 2) / bb_middle * 100
    bb_width_percentile = bb_width.rank(pct=True).iloc[-1] * 100
    
    # Decision logic
    high_vol_conditions = (
        atr_ratio >= 1.15 and          # Strong volatility expansion
        volume_ratio >= 1.4 and       # Consistent volume surges
        bb_width_percentile >= 70     # High volatility expansion
    )
    
    if high_vol_conditions:
        return "high_vol"
    else:
        return "moderate_vol"

def get_adaptive_config(market_regime: str = None, data: pd.DataFrame = None) -> Dict:
    """
    Get configuration based on market regime
    
    Args:
        market_regime: Override regime detection
        data: Market data for regime detection
    """
    
    if market_regime is None and data is not None:
        market_regime = detect_market_regime(data)
    elif market_regime is None:
        market_regime = "moderate_vol"  # Safe default
    
    # Base configuration (common parameters)
    base_config = {
        'strategy_name': f'Atlas Adaptive ({market_regime.replace("_", " ").title()})',
        
        # Technical Indicators (unchanged)
        'ema_fast': 15,
        'ema_slow': 35, 
        'atr_period': 16,
        'rsi_period': 12,
        'volume_period': 25,
        'momentum_period': 10,
        
        # Risk Management (unchanged)
        'min_atr': 2.5,
        'max_atr': 15.0,
        'atr_stop_multiplier': 2.5,
        'risk_reward_ratio': 3.0,
        'position_multiplier': 1.2,
        'risk_per_trade': 0.012,  # 1.2%
        
        # Advanced Features (unchanged)
        'trailing_stop': True,
        'trailing_multiplier': 2.5,
        
        # FTMO Compliance (unchanged)
        'max_daily_loss': 0.05,  # 5%
        'max_total_loss': 0.10,  # 10%
    }
    
    if market_regime == "high_vol":
        # Original "Momentum Master" parameters (11.52% annual)
        regime_config = {
            'description': 'High-volatility regime - Original backtested parameters',
            'expected_annual_return': 11.52,
            'backtested_trades_per_month': 15,
            'win_rate': 45.8,
            
            # Signal Parameters (STRICT - Original)
            'rsi_lower': 35,
            'rsi_upper': 65,
            'exit_rsi': 80,
            'volume_threshold': 1.8,      # STRICT
            'momentum_threshold': 0.0008,
            
            # Volatility Parameters (STRICT - Original)
            'atr_multiplier': 1.2,        # STRICT
            'bb_percentile': 75,          # STRICT
        }
    else:  # moderate_vol
        # Adjusted parameters for moderate volatility
        regime_config = {
            'description': 'Moderate-volatility regime - Live tested parameters',
            'expected_annual_return': 'TBD (Live validated +3.01% in 2h)',
            'backtested_trades_per_month': 'TBD',
            'win_rate': 'TBD (1/1 = 100% in live test)',
            
            # Signal Parameters (RELAXED - For moderate sessions)
            'rsi_lower': 30,
            'rsi_upper': 70,
            'exit_rsi': 80,
            'volume_threshold': 0.6,      # RELAXED
            'momentum_threshold': 0.0008,
            
            # Volatility Parameters (RELAXED - For moderate sessions)  
            'atr_multiplier': 0.8,        # RELAXED
            'bb_percentile': 50,          # RELAXED
        }
    
    # Merge configurations
    return {**base_config, **regime_config, 'market_regime': market_regime}

def validate_regime_switch(current_regime: str, new_regime: str, 
                          switch_count_today: int = 0) -> bool:
    """
    Prevent excessive regime switching within a trading day
    
    Args:
        current_regime: Current active regime
        new_regime: Proposed new regime  
        switch_count_today: Number of switches today
        
    Returns:
        bool: Whether to allow the regime switch
    """
    
    # Prevent excessive switching (max 2 switches per day)
    if switch_count_today >= 2:
        return False
    
    # Require regime to be stable for at least 30 minutes before switching
    # (This would need to be implemented with timestamp tracking)
    
    return current_regime != new_regime

if __name__ == "__main__":
    # Example usage
    print("🔄 ADAPTIVE ATLAS STRATEGY CONFIGURATION")
    print("=" * 50)
    
    # Simulate both regimes
    for regime in ["high_vol", "moderate_vol"]:
        config = get_adaptive_config(market_regime=regime)
        print(f"\n📊 {config['strategy_name']}")
        print(f"   Description: {config['description']}")
        print(f"   Volume Threshold: {config['volume_threshold']}x")
        print(f"   ATR Multiplier: {config['atr_multiplier']}x") 
        print(f"   BB Percentile: {config['bb_percentile']}%")
        print(f"   RSI Range: {config['rsi_lower']}-{config['rsi_upper']}")
        
        if isinstance(config['expected_annual_return'], float):
            print(f"   Expected Return: {config['expected_annual_return']:.2f}%")
        else:
            print(f"   Expected Return: {config['expected_annual_return']}")
