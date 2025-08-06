"""
Utility functions for Atlas Trading System
"""

import os
import json
import logging
from datetime import datetime, time
from typing import Dict, Any, Optional
import pandas as pd

from config.config import config


def setup_logging(log_level: str = None) -> logging.Logger:
    """
    Setup logging configuration
    
    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR)
        
    Returns:
        logging.Logger: Configured logger
    """
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Configure logging
    log_level = log_level or config.monitoring.log_level
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config.monitoring.log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)


def is_trading_session(current_time: time = None) -> bool:
    """
    Check if current time is within trading session
    
    Args:
        current_time: Time to check (defaults to now)
        
    Returns:
        bool: True if within trading session
    """
    
    if current_time is None:
        current_time = datetime.now().time()
    
    session_start = time(14, 30)  # 14:30 GMT
    session_end = time(20, 0)     # 20:00 GMT
    
    return session_start <= current_time <= session_end


def calculate_position_value(price: float, quantity: int, contract_multiplier: float = 1.0) -> float:
    """
    Calculate total position value
    
    Args:
        price: Current price
        quantity: Position quantity
        contract_multiplier: Contract multiplier
        
    Returns:
        float: Position value
    """
    
    return abs(price * quantity * contract_multiplier)


def format_currency(amount: float, currency: str = "GBP") -> str:
    """
    Format currency amount for display
    
    Args:
        amount: Amount to format
        currency: Currency code
        
    Returns:
        str: Formatted currency string
    """
    
    symbol = "£" if currency == "GBP" else "$"
    return f"{symbol}{amount:,.2f}"


def save_trade_to_journal(trade_data: Dict[str, Any]) -> None:
    """
    Save trade data to journal file
    
    Args:
        trade_data: Trade information dictionary
    """
    
    journal_file = config.monitoring.trade_log_file
    
    # Create logs directory if needed
    os.makedirs(os.path.dirname(journal_file), exist_ok=True)
    
    # Convert to DataFrame for easy CSV handling
    df = pd.DataFrame([trade_data])
    
    # Append to existing file or create new one
    if os.path.exists(journal_file):
        df.to_csv(journal_file, mode='a', header=False, index=False)
    else:
        df.to_csv(journal_file, mode='w', header=True, index=False)


def load_trade_journal() -> pd.DataFrame:
    """
    Load trade journal from CSV file
    
    Returns:
        pd.DataFrame: Trade journal data
    """
    
    journal_file = config.monitoring.trade_log_file
    
    if os.path.exists(journal_file):
        return pd.read_csv(journal_file)
    else:
        return pd.DataFrame()


def send_slack_alert(message: str, webhook_url: str = None) -> bool:
    """
    Send alert to Slack channel
    
    Args:
        message: Alert message
        webhook_url: Slack webhook URL
        
    Returns:
        bool: True if sent successfully
    """
    
    try:
        import requests
        
        webhook_url = webhook_url or config.monitoring.slack_webhook_url
        
        if not webhook_url:
            print(f"Slack alert (no webhook): {message}")
            return False
        
        payload = {
            "text": f"🚨 Atlas Trading Alert: {message}",
            "username": "Atlas Bot"
        }
        
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.status_code == 200
        
    except Exception as e:
        print(f"Failed to send Slack alert: {e}")
        return False


def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    """
    Calculate Sharpe ratio from returns series
    
    Args:
        returns: Series of returns
        risk_free_rate: Risk-free rate (annualized)
        
    Returns:
        float: Sharpe ratio
    """
    
    if len(returns) == 0 or returns.std() == 0:
        return 0.0
    
    excess_returns = returns - risk_free_rate / 252  # Daily risk-free rate
    return excess_returns.mean() / returns.std() * (252 ** 0.5)  # Annualized


def calculate_max_drawdown(equity_curve: pd.Series) -> float:
    """
    Calculate maximum drawdown from equity curve
    
    Args:
        equity_curve: Series of equity values
        
    Returns:
        float: Maximum drawdown as percentage
    """
    
    if len(equity_curve) == 0:
        return 0.0
    
    peak = equity_curve.expanding().max()
    drawdown = (equity_curve - peak) / peak
    return abs(drawdown.min())


def validate_trade_parameters(
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    position_size: int
) -> bool:
    """
    Validate trade parameters before execution
    
    Args:
        entry_price: Entry price
        stop_loss: Stop loss price
        take_profit: Take profit price
        position_size: Position size
        
    Returns:
        bool: True if parameters are valid
    """
    
    # Basic validation
    if any(x <= 0 for x in [entry_price, abs(stop_loss), abs(take_profit), position_size]):
        return False
    
    # Check risk-reward ratio
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)
    
    if risk <= 0:
        return False
    
    rr_ratio = reward / risk
    if rr_ratio < config.trading.reward_risk_ratio:
        return False
    
    # Check position size limits
    if position_size > config.trading.max_position_size:
        return False
    
    return True


def get_market_hours_info() -> Dict[str, Any]:
    """
    Get market hours and session information
    
    Returns:
        Dict: Market hours information
    """
    
    now = datetime.now()
    current_time = now.time()
    
    return {
        'current_time': current_time,
        'is_trading_session': is_trading_session(current_time),
        'session_start': time(14, 30),
        'session_end': time(20, 0),
        'minutes_to_open': None,  # Calculate if needed
        'minutes_to_close': None  # Calculate if needed
    }


def create_performance_summary(trades_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Create performance summary from trades DataFrame
    
    Args:
        trades_df: DataFrame with trade data
        
    Returns:
        Dict: Performance summary
    """
    
    if trades_df.empty:
        return {}
    
    # Basic metrics
    total_trades = len(trades_df)
    winning_trades = len(trades_df[trades_df['pnl'] > 0])
    losing_trades = len(trades_df[trades_df['pnl'] < 0])
    
    total_pnl = trades_df['pnl'].sum()
    win_rate = winning_trades / total_trades if total_trades > 0 else 0
    
    # Profit factor
    gross_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
    gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    # Average win/loss
    avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
    avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
    
    return {
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'gross_profit': gross_profit,
        'gross_loss': gross_loss,
        'profit_factor': profit_factor,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'largest_win': trades_df['pnl'].max() if total_trades > 0 else 0,
        'largest_loss': trades_df['pnl'].min() if total_trades > 0 else 0
    }


class PerformanceTracker:
    """
    Track trading performance metrics in real-time
    """
    
    def __init__(self):
        self.trades = []
        self.daily_pnl = {}
        self.equity_curve = []
        
    def add_trade(self, trade_data: Dict[str, Any]) -> None:
        """Add completed trade to tracking"""
        self.trades.append(trade_data)
        
        # Update daily P/L
        trade_date = trade_data.get('date', datetime.now().date())
        if trade_date not in self.daily_pnl:
            self.daily_pnl[trade_date] = 0.0
        self.daily_pnl[trade_date] += trade_data.get('pnl', 0.0)
        
    def get_current_performance(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        if not self.trades:
            return {}
            
        trades_df = pd.DataFrame(self.trades)
        return create_performance_summary(trades_df)
    
    def get_daily_pnl(self, date: Optional[datetime] = None) -> float:
        """Get P/L for specific date"""
        target_date = date.date() if date else datetime.now().date()
        return self.daily_pnl.get(target_date, 0.0)
