"""
FTMO Risk Manager
Comprehensive risk management for FTMO evaluation compliance
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date
import numpy as np
from config.config import config


@dataclass
class RiskMetrics:
    """Risk metrics data structure"""
    daily_pnl: float
    total_drawdown: float
    current_equity: float
    max_position_risk: float
    trades_today: int
    risk_capacity_remaining: float


class FTMORiskManager:
    """
    FTMO-compliant risk management system
    Enforces all FTMO rules and prevents rule violations
    """
    
    def __init__(self):
        self.account_size = config.ftmo.account_size
        self.max_daily_loss = config.ftmo.max_daily_loss
        self.max_total_loss = config.ftmo.max_total_loss
        self.max_trade_risk = config.ftmo.max_trade_risk
        
        # Daily tracking
        self.daily_pnl_history: Dict[date, float] = {}
        self.daily_trade_count: Dict[date, int] = {}
        
        # Risk state
        self.peak_equity = self.account_size
        self.current_drawdown = 0.0
        self.is_risk_breach = False
        self.breach_reason = ""
        
    def can_open_trade(
        self, 
        current_daily_pnl: float, 
        current_drawdown: float,
        proposed_risk: float = None
    ) -> bool:
        """
        Check if a new trade can be opened based on risk limits
        
        Args:
            current_daily_pnl: Current day's P/L
            current_drawdown: Current equity drawdown percentage
            proposed_risk: Risk amount for the proposed trade
            
        Returns:
            bool: True if trade can be opened, False otherwise
        """
        
        # Check daily loss limit
        if current_daily_pnl <= -self.max_daily_loss:
            self.breach_reason = f"Daily loss limit exceeded: {current_daily_pnl:.2f}"
            return False
            
        # Check total drawdown limit
        if current_drawdown >= config.ftmo.max_total_loss_pct:
            self.breach_reason = f"Total drawdown limit exceeded: {current_drawdown:.2%}"
            return False
            
        # Check proposed trade risk
        if proposed_risk and proposed_risk > self.max_trade_risk:
            self.breach_reason = f"Trade risk exceeds limit: {proposed_risk:.2f} > {self.max_trade_risk:.2f}"
            return False
            
        # Check if adding proposed risk would exceed daily limit
        if proposed_risk and (current_daily_pnl - proposed_risk) <= -self.max_daily_loss:
            self.breach_reason = f"Proposed trade would exceed daily loss limit"
            return False
            
        return True
    
    def calculate_max_position_risk(
        self, 
        current_daily_pnl: float, 
        current_equity: float
    ) -> float:
        """
        Calculate maximum allowable risk for next position
        
        Args:
            current_daily_pnl: Current day's P/L
            current_equity: Current account equity
            
        Returns:
            float: Maximum risk amount in account currency
        """
        
        # Risk remaining for the day
        daily_risk_remaining = self.max_daily_loss + current_daily_pnl
        
        # Risk remaining for total account
        total_risk_remaining = self.max_total_loss - (self.account_size - current_equity)
        
        # Maximum single trade risk
        max_trade_risk = self.max_trade_risk
        
        # Take the minimum of all constraints
        max_risk = min(daily_risk_remaining, total_risk_remaining, max_trade_risk)
        
        return max(0, max_risk)  # Never allow negative risk
    
    def update_equity_peak(self, current_equity: float) -> None:
        """Update equity high-water mark"""
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
            
    def calculate_drawdown(self, current_equity: float) -> float:
        """Calculate current drawdown percentage"""
        if self.peak_equity <= 0:
            return 0.0
            
        drawdown = (self.peak_equity - current_equity) / self.account_size
        return max(0.0, drawdown)
    
    def is_margin_call_risk(self, current_equity: float) -> bool:
        """Check if account is at risk of margin call"""
        margin_threshold = self.account_size * config.ftmo.margin_call_threshold
        return current_equity <= margin_threshold
    
    def get_risk_metrics(
        self, 
        current_equity: float, 
        current_daily_pnl: float,
        open_position_risk: float = 0.0,
        trades_today: int = 0
    ) -> RiskMetrics:
        """
        Get comprehensive risk metrics
        
        Args:
            current_equity: Current account equity
            current_daily_pnl: Current day's P/L
            open_position_risk: Risk from currently open positions
            trades_today: Number of trades executed today
            
        Returns:
            RiskMetrics: Comprehensive risk metrics
        """
        
        self.update_equity_peak(current_equity)
        total_drawdown = self.calculate_drawdown(current_equity)
        risk_capacity = self.calculate_max_position_risk(current_daily_pnl, current_equity)
        
        return RiskMetrics(
            daily_pnl=current_daily_pnl,
            total_drawdown=total_drawdown,
            current_equity=current_equity,
            max_position_risk=open_position_risk,
            trades_today=trades_today,
            risk_capacity_remaining=risk_capacity
        )
    
    def validate_ftmo_compliance(self, risk_metrics: RiskMetrics) -> Tuple[bool, List[str]]:
        """
        Validate full FTMO compliance
        
        Args:
            risk_metrics: Current risk metrics
            
        Returns:
            Tuple[bool, List[str]]: (is_compliant, list_of_violations)
        """
        
        violations = []
        
        # Daily loss check
        if risk_metrics.daily_pnl <= -self.max_daily_loss:
            violations.append(f"Daily loss limit exceeded: {risk_metrics.daily_pnl:.2f}")
            
        # Total drawdown check
        if risk_metrics.total_drawdown >= config.ftmo.max_total_loss_pct:
            violations.append(f"Total drawdown limit exceeded: {risk_metrics.total_drawdown:.2%}")
            
        # Margin call risk check
        if self.is_margin_call_risk(risk_metrics.current_equity):
            violations.append(f"Margin call risk: equity below 90% threshold")
            
        # Single trade risk check
        if risk_metrics.max_position_risk > self.max_trade_risk:
            violations.append(f"Position risk too high: {risk_metrics.max_position_risk:.2f}")
            
        # Trading frequency check (optional - can add daily trade limits)
        max_daily_trades = config.trading.max_trades_per_day
        if risk_metrics.trades_today > max_daily_trades:
            violations.append(f"Daily trade limit exceeded: {risk_metrics.trades_today}")
            
        is_compliant = len(violations) == 0
        return is_compliant, violations
    
    def emergency_stop(self, reason: str) -> None:
        """
        Emergency stop all trading due to risk breach
        
        Args:
            reason: Reason for emergency stop
        """
        self.is_risk_breach = True
        self.breach_reason = reason
        print(f"EMERGENCY STOP TRIGGERED: {reason}")
        
    def reset_daily_limits(self) -> None:
        """Reset daily risk tracking (call at start of each trading day)"""
        today = date.today()
        if today not in self.daily_pnl_history:
            self.daily_pnl_history[today] = 0.0
            self.daily_trade_count[today] = 0
            
    def log_trade_result(self, pnl: float, trade_date: date = None) -> None:
        """
        Log trade result for risk tracking
        
        Args:
            pnl: Trade P/L
            trade_date: Date of trade (defaults to today)
        """
        if trade_date is None:
            trade_date = date.today()
            
        if trade_date not in self.daily_pnl_history:
            self.daily_pnl_history[trade_date] = 0.0
            self.daily_trade_count[trade_date] = 0
            
        self.daily_pnl_history[trade_date] += pnl
        self.daily_trade_count[trade_date] += 1
    
    def get_daily_statistics(self, days: int = 30) -> Dict[str, float]:
        """
        Get daily trading statistics
        
        Args:
            days: Number of recent days to analyze
            
        Returns:
            Dict: Daily statistics
        """
        recent_dates = sorted(self.daily_pnl_history.keys())[-days:]
        recent_pnls = [self.daily_pnl_history[d] for d in recent_dates]
        
        if not recent_pnls:
            return {}
            
        return {
            'avg_daily_pnl': np.mean(recent_pnls),
            'daily_pnl_std': np.std(recent_pnls),
            'max_daily_gain': max(recent_pnls),
            'max_daily_loss': min(recent_pnls),
            'positive_days': sum(1 for pnl in recent_pnls if pnl > 0),
            'negative_days': sum(1 for pnl in recent_pnls if pnl < 0),
            'win_rate': sum(1 for pnl in recent_pnls if pnl > 0) / len(recent_pnls) if recent_pnls else 0
        }


class PositionRiskCalculator:
    """
    Calculate position-specific risk metrics
    """
    
    @staticmethod
    def calculate_stop_loss_risk(
        entry_price: float, 
        stop_loss_price: float, 
        position_size: float,
        contract_multiplier: float = 1.0
    ) -> float:
        """
        Calculate risk amount for a position with stop loss
        
        Args:
            entry_price: Entry price
            stop_loss_price: Stop loss price
            position_size: Position size (number of contracts/shares)
            contract_multiplier: Contract multiplier (e.g., 1 for CFD, 20 for NQ)
            
        Returns:
            float: Risk amount in account currency
        """
        price_diff = abs(entry_price - stop_loss_price)
        risk_amount = price_diff * position_size * contract_multiplier
        return risk_amount
    
    @staticmethod
    def calculate_reward_risk_ratio(
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float
    ) -> float:
        """
        Calculate reward-to-risk ratio
        
        Args:
            entry_price: Entry price
            stop_loss_price: Stop loss price
            take_profit_price: Take profit price
            
        Returns:
            float: Reward-to-risk ratio
        """
        risk = abs(entry_price - stop_loss_price)
        reward = abs(take_profit_price - entry_price)
        
        if risk == 0:
            return 0.0
            
        return reward / risk
    
    @staticmethod
    def calculate_position_value(
        price: float,
        position_size: float,
        contract_multiplier: float = 1.0
    ) -> float:
        """
        Calculate total position value
        
        Args:
            price: Current price
            position_size: Position size
            contract_multiplier: Contract multiplier
            
        Returns:
            float: Position value
        """
        return price * position_size * contract_multiplier
