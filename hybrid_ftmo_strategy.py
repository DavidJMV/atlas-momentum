#!/usr/bin/env python3
"""
FTMO-Optimized Hybrid Strategy
Uses original parameters primarily, switches to moderate only when necessary
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

from typing import Dict, Literal
import pandas as pd
import numpy as np

def get_hybrid_ftmo_config(force_regime: str = None) -> Dict:
    """
    Get FTMO-optimized configuration that balances performance and activity
    
    Strategy:
    - Primary: Original "Momentum Master" parameters (11.52% proven)
    - Fallback: Moderate parameters (only when volatility is very low)
    - Constraint: Maximum 20% of time in moderate mode
    
    Args:
        force_regime: Override auto-detection ("high_selectivity" or "moderate_selectivity")
    """
    
    # Base configuration (unchanged - proven effective)
    base_config = {
        'strategy_name': 'FTMO Hybrid Atlas',
        'description': 'Primarily strict parameters with moderate fallback',
        
        # Core indicators (proven optimal)
        'ema_fast': 15,
        'ema_slow': 35,
        'atr_period': 16,
        'rsi_period': 12,
        'volume_period': 25,
        'momentum_period': 10,
        
        # Risk management (unchanged - FTMO compliant)
        'min_atr': 2.5,
        'max_atr': 15.0,
        'atr_stop_multiplier': 2.5,
        'risk_reward_ratio': 3.0,
        'position_multiplier': 1.2,
        'risk_per_trade': 0.012,  # 1.2%
        
        # FTMO compliance
        'max_daily_loss': 0.05,  # 5%
        'max_total_loss': 0.10,  # 10%
        'exit_rsi': 80,
        
        # Regime switching controls
        'max_moderate_time_percentage': 20,  # Only 20% of time in moderate mode
        'regime_switch_cooldown_minutes': 30,  # Prevent excessive switching
        'require_volatility_confirmation': True,
    }
    
    # Determine regime (default to high selectivity)
    regime = force_regime or "high_selectivity"
    
    if regime == "high_selectivity":
        # PRIMARY MODE: Original "Momentum Master" parameters
        regime_params = {
            'description': 'High-selectivity mode (Primary) - Original 11.52% parameters',
            'mode': 'primary',
            'expected_annual_return': 11.52,
            'expected_trades_per_month': 15,
            'target_win_rate': 45.8,
            
            # Signal parameters (STRICT - Proven)
            'rsi_lower': 35,
            'rsi_upper': 65,
            'volume_threshold': 1.8,      # STRICT - Quality over quantity
            'momentum_threshold': 0.0008,
            
            # Volatility parameters (STRICT - Proven)
            'atr_multiplier': 1.2,        # STRICT - Only high-conviction setups
            'bb_percentile': 75,          # STRICT - Strong expansion required
        }
    else:  # moderate_selectivity
        # FALLBACK MODE: Only when absolutely necessary
        regime_params = {
            'description': 'Moderate-selectivity mode (Fallback) - Emergency use only',
            'mode': 'fallback',
            'expected_annual_return': 'Unknown (use sparingly)',
            'expected_trades_per_month': 'TBD',
            'target_win_rate': 'TBD',
            
            # Signal parameters (RELAXED - Use sparingly)
            'rsi_lower': 32,              # Slightly relaxed from 30
            'rsi_upper': 68,              # Slightly relaxed from 70
            'volume_threshold': 1.0,      # More relaxed than 0.6 but less than 1.8
            'momentum_threshold': 0.0008,
            
            # Volatility parameters (RELAXED - Use sparingly)
            'atr_multiplier': 1.0,        # More relaxed than 0.8 but less than 1.2
            'bb_percentile': 60,          # More relaxed than 50 but less than 75
        }
    
    return {**base_config, **regime_params, 'regime': regime}

def should_switch_to_moderate(market_data: pd.DataFrame, 
                             current_regime: str,
                             moderate_time_today: int = 0,
                             daily_trades_so_far: int = 0) -> tuple[bool, str]:
    """
    Determine if we should switch to moderate parameters
    
    Args:
        market_data: Recent market data for analysis
        current_regime: Current active regime
        moderate_time_today: Minutes in moderate mode today
        daily_trades_so_far: Trades executed today
        
    Returns:
        (should_switch, reason)
    """
    
    # Safety constraints
    session_minutes = 5.5 * 60  # 330 minutes per session
    max_moderate_minutes = session_minutes * 0.2  # 20% max
    
    # Don't switch if already at limit
    if moderate_time_today >= max_moderate_minutes:
        return False, "Moderate time limit reached for today"
    
    # Don't switch if we already have trades today
    if daily_trades_so_far >= 2:
        return False, "Sufficient trading activity today"
    
    # Only switch if we're currently in high selectivity mode
    if current_regime != "high_selectivity":
        return False, "Already in moderate mode"
    
    # Check if it's late in the session with no trades
    current_time = market_data.index[-1].time()
    if current_time.hour >= 18 and daily_trades_so_far == 0:
        return True, "Late session emergency - no trades yet"
    
    # Check for extremely low volatility
    if len(market_data) >= 50:
        recent_data = market_data.tail(50)
        
        # Calculate volatility metrics
        returns = recent_data['close'].pct_change().dropna()
        current_vol = returns.std() * np.sqrt(1440)  # Annualized
        
        # ATR analysis
        high = recent_data['high']
        low = recent_data['low']
        close = recent_data['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=14).mean()
        
        atr_ratio = atr.iloc[-1] / atr.mean() if len(atr) > 14 else 1.0
        
        # Volume analysis
        volume_ma = recent_data['volume'].rolling(window=20).mean()
        volume_ratio = recent_data['volume'].iloc[-1] / volume_ma.iloc[-1]
        
        # Switch conditions (very conservative)
        if (atr_ratio < 0.7 and           # Very low volatility
            volume_ratio < 0.8 and        # Low volume
            current_vol < 0.01 and        # Very low price volatility
            current_time.hour >= 17):     # Later in session
            
            return True, f"Extremely low volatility session (ATR: {atr_ratio:.2f}, Vol: {volume_ratio:.2f})"
    
    return False, "Conditions don't warrant moderate parameters"

def get_recommended_ftmo_strategy() -> Dict:
    """Get the recommended strategy for FTMO evaluation"""
    
    print("🎯 FTMO STRATEGY RECOMMENDATION")
    print("Based on validation results")
    print("=" * 35)
    
    # Primary configuration
    config = get_hybrid_ftmo_config("high_selectivity")
    
    print(f"✅ PRIMARY MODE: {config['description']}")
    print(f"   Expected Return: {config['expected_annual_return']}%")
    print(f"   Volume Threshold: {config['volume_threshold']}x")
    print(f"   ATR Multiplier: {config['atr_multiplier']}x")
    print(f"   BB Percentile: {config['bb_percentile']}%")
    print(f"   RSI Range: {config['rsi_lower']}-{config['rsi_upper']}")
    
    # Fallback configuration
    fallback_config = get_hybrid_ftmo_config("moderate_selectivity")
    
    print(f"\n⚠️  FALLBACK MODE: {fallback_config['description']}")
    print(f"   Usage: Max {config['max_moderate_time_percentage']}% of trading time")
    print(f"   Volume Threshold: {fallback_config['volume_threshold']}x")
    print(f"   ATR Multiplier: {fallback_config['atr_multiplier']}x")
    print(f"   BB Percentile: {fallback_config['bb_percentile']}%")
    print(f"   RSI Range: {fallback_config['rsi_lower']}-{fallback_config['rsi_upper']}")
    
    print(f"\n💡 STRATEGY LOGIC")
    print("-" * 15)
    print("1. Start each day with PRIMARY parameters (proven 11.52%)")
    print("2. Only switch to FALLBACK if:")
    print("   • Very late in session with no trades")
    print("   • Extremely low volatility detected")
    print("   • Haven't used >20% fallback time today")
    print("3. Switch back to PRIMARY as soon as conditions improve")
    
    print(f"\n🎯 FTMO EVALUATION BENEFITS")
    print("-" * 25)
    print("✅ Maintains proven 11.52% annual return potential")
    print("✅ Reduces risk of zero-trade days")
    print("✅ Limits moderate parameter usage to 20% max")
    print("✅ Keeps drawdown risk manageable")
    print("✅ Preserves strategy edge while ensuring activity")
    
    return config

if __name__ == "__main__":
    recommended_config = get_recommended_ftmo_strategy()
    
    print(f"\n🚀 NEXT STEPS")
    print("-" * 12)
    print("1. Implement this hybrid approach in realtime_strategy_test.py")
    print("2. Test with regime switching logic")
    print("3. Validate with Monte Carlo analysis")
    print("4. Deploy to FTMO evaluation with confidence")
