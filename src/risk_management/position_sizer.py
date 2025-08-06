"""
FTMO Position Sizer
Calculates optimal position sizes for FTMO compliance
"""

from typing import Optional
import math
from config.config import config
from .risk_manager import PositionRiskCalculator


class FTMOPositionSizer:
    """
    Position sizing system optimized for FTMO evaluation
    Ensures compliance with all risk limits while maximizing capital efficiency
    """
    
    def __init__(self):
        self.max_trade_risk = config.ftmo.max_trade_risk
        self.initial_position_size = config.trading.initial_position_size
        self.max_position_size = config.trading.max_position_size
        self.scaling_threshold_pnl = config.trading.scaling_threshold_pnl
        self.scaling_max_drawdown = config.trading.scaling_max_drawdown
        
    def calculate_size(
        self,
        entry_price: float,
        stop_loss_price: float,
        current_equity: float,
        realized_pnl: float = 0.0,
        current_drawdown: float = 0.0,
        max_risk_override: Optional[float] = None
    ) -> int:
        """
        Calculate optimal position size for the trade
        
        Args:
            entry_price: Planned entry price
            stop_loss_price: Stop loss price
            current_equity: Current account equity
            realized_pnl: Realized P/L to date
            current_drawdown: Current equity drawdown
            max_risk_override: Override max risk (if provided)
            
        Returns:
            int: Position size (number of contracts)
        """
        
        # Determine maximum allowable position size based on scaling rules
        max_contracts = self._get_max_contracts(realized_pnl, current_drawdown)
        
        # Calculate risk per contract
        risk_per_contract = abs(entry_price - stop_loss_price)
        
        if risk_per_contract <= 0:
            return 0
            
        # Determine maximum risk for this trade
        max_risk = max_risk_override or self._calculate_max_risk(current_equity)
        
        # Calculate position size based on risk
        calculated_size = math.floor(max_risk / risk_per_contract)
        
        # Apply position size constraints
        position_size = min(calculated_size, max_contracts)
        
        # Ensure minimum viable position (at least 1 contract if affordable)
        if position_size == 0 and risk_per_contract <= max_risk:
            position_size = 1
            
        return max(0, position_size)
    
    def _get_max_contracts(self, realized_pnl: float, current_drawdown: float) -> int:
        """
        Determine maximum number of contracts based on scaling rules
        
        Args:
            realized_pnl: Realized P/L to date
            current_drawdown: Current equity drawdown
            
        Returns:
            int: Maximum allowed contracts
        """
        
        # Start with initial position size
        max_contracts = self.initial_position_size
        
        # Check if we can scale up to 2 contracts
        if (realized_pnl >= self.scaling_threshold_pnl and 
            current_drawdown <= self.scaling_max_drawdown):
            max_contracts = self.max_position_size
            
        return max_contracts
    
    def _calculate_max_risk(self, current_equity: float) -> float:
        """
        Calculate maximum risk amount for this trade
        
        Args:
            current_equity: Current account equity
            
        Returns:
            float: Maximum risk amount
        """
        
        # Base risk limit
        base_risk = self.max_trade_risk
        
        # Reduce risk if equity is low
        equity_factor = min(1.0, current_equity / config.ftmo.account_size)
        adjusted_risk = base_risk * equity_factor
        
        # Additional safety buffer (use 90% of calculated risk)
        safety_buffer = 0.90
        final_risk = adjusted_risk * safety_buffer
        
        return final_risk
    
    def calculate_stop_loss_distance(
        self,
        entry_price: float,
        atr_value: float,
        max_risk_amount: float,
        position_size: int = 1
    ) -> float:
        """
        Calculate optimal stop loss distance
        
        Args:
            entry_price: Entry price
            atr_value: Current ATR value
            max_risk_amount: Maximum risk amount allowed
            position_size: Planned position size
            
        Returns:
            float: Stop loss distance from entry
        """
        
        # ATR-based stop distance
        atr_stop_distance = config.trading.stop_loss_atr_mult * atr_value
        
        # Risk-based stop distance
        risk_stop_distance = max_risk_amount / position_size if position_size > 0 else atr_stop_distance
        
        # Use the smaller of the two (more conservative)
        stop_distance = min(atr_stop_distance, risk_stop_distance)
        
        # Ensure minimum stop distance (0.1% of entry price)
        min_stop_distance = entry_price * 0.001
        stop_distance = max(stop_distance, min_stop_distance)
        
        return stop_distance
    
    def validate_position_risk(
        self,
        entry_price: float,
        stop_loss_price: float,
        position_size: int,
        current_equity: float
    ) -> bool:
        """
        Validate that position risk is within acceptable limits
        
        Args:
            entry_price: Entry price
            stop_loss_price: Stop loss price
            position_size: Position size
            current_equity: Current account equity
            
        Returns:
            bool: True if position risk is acceptable
        """
        
        # Calculate position risk
        risk_amount = PositionRiskCalculator.calculate_stop_loss_risk(
            entry_price, stop_loss_price, position_size
        )
        
        # Check against maximum trade risk
        if risk_amount > self.max_trade_risk:
            return False
            
        # Check against equity percentage (max 1% of equity per trade)
        max_equity_risk = current_equity * 0.01
        if risk_amount > max_equity_risk:
            return False
            
        return True
    
    def calculate_take_profit_distance(
        self,
        stop_loss_distance: float,
        reward_risk_ratio: Optional[float] = None
    ) -> float:
        """
        Calculate take profit distance based on reward-risk ratio
        
        Args:
            stop_loss_distance: Stop loss distance
            reward_risk_ratio: Target reward-risk ratio
            
        Returns:
            float: Take profit distance from entry
        """
        
        target_rr = reward_risk_ratio or config.trading.reward_risk_ratio
        return stop_loss_distance * target_rr
    
    def get_position_sizing_info(
        self,
        entry_price: float,
        stop_loss_price: float,
        current_equity: float,
        realized_pnl: float = 0.0,
        current_drawdown: float = 0.0
    ) -> dict:
        """
        Get comprehensive position sizing information
        
        Args:
            entry_price: Planned entry price
            stop_loss_price: Stop loss price
            current_equity: Current account equity
            realized_pnl: Realized P/L to date
            current_drawdown: Current equity drawdown
            
        Returns:
            dict: Position sizing information
        """
        
        position_size = self.calculate_size(
            entry_price, stop_loss_price, current_equity, 
            realized_pnl, current_drawdown
        )
        
        risk_amount = PositionRiskCalculator.calculate_stop_loss_risk(
            entry_price, stop_loss_price, position_size
        )
        
        take_profit_distance = self.calculate_take_profit_distance(
            abs(entry_price - stop_loss_price)
        )
        
        if entry_price > stop_loss_price:  # Long position
            take_profit_price = entry_price + take_profit_distance
        else:  # Short position
            take_profit_price = entry_price - take_profit_distance
            
        reward_amount = abs(take_profit_price - entry_price) * position_size
        
        return {
            'position_size': position_size,
            'risk_amount': risk_amount,
            'reward_amount': reward_amount,
            'reward_risk_ratio': reward_amount / risk_amount if risk_amount > 0 else 0,
            'risk_percentage': (risk_amount / current_equity) * 100 if current_equity > 0 else 0,
            'take_profit_price': take_profit_price,
            'max_contracts_allowed': self._get_max_contracts(realized_pnl, current_drawdown),
            'is_risk_acceptable': self.validate_position_risk(
                entry_price, stop_loss_price, position_size, current_equity
            )
        }


class DynamicPositionSizer:
    """
    Advanced position sizer with dynamic risk adjustment
    """
    
    def __init__(self):
        self.base_sizer = FTMOPositionSizer()
        
    def calculate_dynamic_size(
        self,
        entry_price: float,
        stop_loss_price: float,
        current_equity: float,
        volatility_factor: float = 1.0,
        confidence_factor: float = 1.0,
        recent_win_rate: float = 0.5
    ) -> int:
        """
        Calculate position size with dynamic adjustments
        
        Args:
            entry_price: Entry price
            stop_loss_price: Stop loss price
            current_equity: Current equity
            volatility_factor: Market volatility adjustment (0.5-2.0)
            confidence_factor: Signal confidence adjustment (0.5-1.5)
            recent_win_rate: Recent win rate (0.0-1.0)
            
        Returns:
            int: Adjusted position size
        """
        
        # Calculate base position size
        base_size = self.base_sizer.calculate_size(
            entry_price, stop_loss_price, current_equity
        )
        
        # Apply dynamic adjustments
        volatility_adjustment = 1.0 / volatility_factor  # Reduce size in high volatility
        confidence_adjustment = confidence_factor
        win_rate_adjustment = 0.5 + (recent_win_rate * 0.5)  # 0.5-1.0 range
        
        # Combined adjustment factor
        total_adjustment = (
            volatility_adjustment * 
            confidence_adjustment * 
            win_rate_adjustment
        )
        
        # Apply adjustment (capped between 0.25 and 1.5)
        adjustment_factor = max(0.25, min(1.5, total_adjustment))
        adjusted_size = math.floor(base_size * adjustment_factor)
        
        # Ensure at least 1 contract if base size was positive
        if base_size > 0 and adjusted_size == 0:
            adjusted_size = 1
            
        return max(0, adjusted_size)
