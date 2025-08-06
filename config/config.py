"""
FTMO Trading Strategy Configuration
Atlas Momentum Breakout System
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import os
from enum import Enum

class TradingSession(Enum):
    LONDON = "london"
    US_OVERLAP = "us_overlap"
    US_CLOSE = "us_close"

@dataclass
class FTMOConfig:
    """FTMO Evaluation Configuration"""
    # Account Settings
    account_size: float = 50000.0  # £50k account
    leverage: float = 100.0
    currency: str = "GBP"
    
    # FTMO Rules
    profit_target_pct: float = 0.10  # 10%
    max_daily_loss_pct: float = 0.05  # 5%
    max_total_loss_pct: float = 0.10  # 10%
    evaluation_days: int = 30
    no_overnight_holds: bool = True
    
    # Risk Limits (in GBP)
    max_daily_loss: float = 2500.0  # 5% of £50k
    max_total_loss: float = 5000.0  # 10% of £50k
    max_trade_risk: float = 250.0
    margin_call_threshold: float = 0.90  # 90% of starting balance

@dataclass
class TradingConfig:
    """Core Trading Strategy Configuration"""
    # Primary Instrument
    symbol: str = "NQ"  # NASDAQ-100 CFD
    timeframe: str = "1m"
    
    # Position Sizing
    initial_position_size: int = 1  # 1 NQ CFD
    max_position_size: int = 2  # Scale to 2 only after conditions met
    scaling_threshold_pnl: float = 2000.0  # £2k realized P/L
    scaling_max_drawdown: float = 0.01  # 1% equity drawdown
    
    # Technical Indicators
    atr_period: int = 14
    atr_lookback: int = 50
    atr_multiplier: float = 1.2
    ema_fast: int = 21
    ema_slow: int = 50
    rsi_period: int = 14
    rsi_long_min: float = 45.0
    rsi_long_max: float = 75.0
    rsi_short_min: float = 25.0
    rsi_short_max: float = 55.0
    volume_multiplier: float = 1.5
    volume_period: int = 20
    bb_period: int = 20
    bb_percentile: float = 75.0
    
    # Risk Management
    stop_loss_atr_mult: float = 2.5
    reward_risk_ratio: float = 1.8
    trailing_stop_atr_mult: float = 1.5
    trailing_activation_mult: float = 1.2
    
    # Trading Hours (GMT)
    session_start: str = "14:30"  # US session overlap
    session_end: str = "20:00"   # Before US close
    close_before_end_minutes: int = 30
    
    # Trade Management
    max_trades_per_day: int = 3
    min_gap_between_trades_minutes: int = 60
    avoid_first_last_minutes: int = 30

@dataclass
class BrokerConfig:
    """Pepperstone cTrader Configuration"""
    broker: str = "Pepperstone"
    platform: str = "cTrader"
    api_url: str = "https://api.pepperstone.com"
    
    # Trading Costs
    commission_per_lot: float = 4.50  # £4.50 round-turn
    typical_spread: float = 0.5  # 0.5 points
    expected_slippage: int = 1  # 1 tick
    
    # Connection Settings
    max_latency_ms: int = 150
    reconnect_attempts: int = 3
    heartbeat_interval: int = 30

@dataclass
class BacktestConfig:
    """Backtesting Configuration"""
    # Data Settings
    start_date: str = "2021-01-01"
    end_date: str = "2024-12-31"
    out_of_sample_start: str = "2025-01-01"
    out_of_sample_end: str = "2025-08-06"
    
    # Walk-Forward Settings
    train_months: int = 6
    test_months: int = 3
    step_months: int = 3
    
    # Optimization
    optimization_metric: str = "pass_rate"  # vs sharpe, calmar, etc.
    min_trades: int = 10  # Minimum trades for valid test
    
    # Monte Carlo
    mc_runs: int = 1000
    random_seed: int = 42

@dataclass
class MonitoringConfig:
    """Monitoring and Alerting Configuration"""
    # Slack Configuration
    slack_webhook_url: str = os.getenv("SLACK_WEBHOOK_URL", "")
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/atlas_trading.log"
    trade_log_file: str = "logs/trade_journal.csv"
    
    # Alerts
    alert_on_trade: bool = True
    alert_on_error: bool = True
    alert_on_daily_loss_pct: float = 0.03  # Alert at 3% daily loss
    alert_on_equity_drawdown_pct: float = 0.05  # Alert at 5% drawdown

# Master Configuration
@dataclass  
class Config:
    """Master Configuration Class"""
    ftmo: FTMOConfig = None
    trading: TradingConfig = None
    broker: BrokerConfig = None
    backtest: BacktestConfig = None
    monitoring: MonitoringConfig = None
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        # Initialize defaults if None
        if self.ftmo is None:
            self.ftmo = FTMOConfig()
        if self.trading is None:
            self.trading = TradingConfig()
        if self.broker is None:
            self.broker = BrokerConfig()
        if self.backtest is None:
            self.backtest = BacktestConfig()
        if self.monitoring is None:
            self.monitoring = MonitoringConfig()
            
        self._validate_config()
    
    def _validate_config(self):
        """Validate configuration parameters"""
        # FTMO validation
        assert 0 < self.ftmo.profit_target_pct <= 1.0
        assert 0 < self.ftmo.max_daily_loss_pct <= 1.0
        assert 0 < self.ftmo.max_total_loss_pct <= 1.0
        
        # Trading validation
        assert self.trading.reward_risk_ratio >= 1.0
        assert self.trading.max_position_size >= self.trading.initial_position_size
        assert 0 < self.trading.scaling_max_drawdown <= 1.0
        
        # Risk validation
        assert self.ftmo.max_trade_risk <= self.ftmo.max_daily_loss
        assert self.ftmo.max_daily_loss <= self.ftmo.max_total_loss

# Global configuration instance
config = Config()

# Environment-specific overrides
if os.getenv("ENVIRONMENT") == "production":
    config.monitoring.log_level = "WARNING"
    config.monitoring.alert_on_trade = True
elif os.getenv("ENVIRONMENT") == "development":
    config.monitoring.log_level = "DEBUG"
    config.monitoring.alert_on_trade = False
