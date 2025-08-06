"""
Enhanced Paper Trading Engine with Real Market Data Integration
Production-ready paper trading system for Atlas Strategy
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
import pandas as pd
import json
from pathlib import Path

from config.config import config
from strategies.atlas_momentum import AtlasMomentumStrategy
from risk_management.risk_manager import FTMORiskManager
from risk_management.position_sizer import FTMOPositionSizer

# Try to import real data feed components
try:
    from data.real_data_feed import DataFeedManager, MarketData
    REAL_DATA_AVAILABLE = True
    print("✅ Real market data integration available")
except ImportError:
    REAL_DATA_AVAILABLE = False
    print("⚠️  Real market data not available - using simulation")
    # Create minimal MarketData structure for fallback
    @dataclass
    class MarketData:
        symbol: str
        timestamp: datetime
        open: float
        high: float
        low: float
        close: float
        volume: int
        bid: Optional[float] = None
        ask: Optional[float] = None


@dataclass
class PaperTrade:
    """Paper trade record with enhanced tracking"""
    trade_id: str
    timestamp: datetime
    symbol: str
    action: str  # "BUY" or "SELL" 
    quantity: int
    price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    exit_price: Optional[float] = None
    exit_timestamp: Optional[datetime] = None
    pnl: float = 0.0
    commission: float = 0.0
    status: str = "OPEN"  # "OPEN", "CLOSED", "CANCELLED"


@dataclass
class Position:
    """Trading position with real-time P&L tracking"""
    symbol: str
    quantity: int
    entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    entry_time: datetime = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    def __post_init__(self):
        if self.entry_time is None:
            self.entry_time = datetime.now()
            
    def update_price(self, new_price: float) -> float:
        """Update position with new price and return P&L change"""
        old_pnl = self.unrealized_pnl
        self.current_price = new_price
        if self.quantity != 0:
            self.unrealized_pnl = (new_price - self.entry_price) * self.quantity
        return self.unrealized_pnl - old_pnl


class SimulatedDataProvider:
    """Fallback simulated data provider when real data unavailable"""
    
    def __init__(self):
        self.current_price = 15800.0  # Starting NQ price
        self.volatility = 0.0015  # 0.15% per update
        self.trend = 0.0001  # Slight upward bias
        
    def generate_tick(self, symbol: str) -> MarketData:
        """Generate realistic market tick"""
        import random
        
        # Random walk with trend and volatility
        change = random.gauss(self.trend, self.volatility)
        self.current_price *= (1 + change)
        
        # Keep price in reasonable range
        self.current_price = max(15000, min(16500, self.current_price))
        
        # Generate spread and volume
        spread = 0.25
        volume = random.randint(50, 500)
        
        return MarketData(
            symbol=symbol,
            timestamp=datetime.now(),
            open=self.current_price,
            high=self.current_price + random.uniform(0, 1.0),
            low=self.current_price - random.uniform(0, 1.0),
            close=self.current_price,
            volume=volume,
            bid=self.current_price - spread/2,
            ask=self.current_price + spread/2
        )


class EnhancedPaperTradingEngine:
    """
    Production-ready paper trading engine with real market data
    """
    
    def __init__(self, 
                 initial_balance: float = 50000.0,
                 enable_real_data: bool = True,
                 log_file: str = "enhanced_paper_trading.log"):
        
        # Account setup
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.equity = initial_balance
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0
        self.daily_pnl = 0.0
        self.max_drawdown = 0.0
        self.peak_equity = initial_balance
        
        # Positions and trades
        self.positions: Dict[str, Position] = {}
        self.trades: List[PaperTrade] = []
        self.trade_counter = 0
        
        # Strategy and risk management
        self.strategy = AtlasMomentumStrategy()
        self.risk_manager = FTMORiskManager()
        self.position_sizer = FTMOPositionSizer()
        
        # Data feed setup
        self.enable_real_data = enable_real_data and REAL_DATA_AVAILABLE
        if self.enable_real_data:
            self.data_provider = DataFeedManager()
            self.data_provider.subscribe(self._on_market_data)
        else:
            self.data_provider = SimulatedDataProvider()
            
        # Market data storage for strategy calculations
        self.price_history: List[Dict] = []
        self.max_history_length = 1000
        
        # Trading state
        self.is_running = False
        self.last_signal_check = None
        self.signal_check_interval = 30  # seconds
        
        # Performance tracking
        self.start_time = None
        self.session_trades = 0
        self.winning_trades = 0
        
        # Logging setup
        self.log_file = log_file
        self._setup_logging()
        
        self.logger.info("Enhanced Paper Trading Engine initialized")
        self.logger.info(f"Real data enabled: {self.enable_real_data}")
        self.logger.info(f"Initial balance: ${initial_balance:,.2f}")
        
    def _setup_logging(self):
        """Setup comprehensive logging"""
        # Create logs directory if it doesn't exist
        Path("logs").mkdir(exist_ok=True)
        
        # Configure logger
        self.logger = logging.getLogger("PaperTrading")
        self.logger.setLevel(logging.INFO)
        
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
            
        # File handler
        file_handler = logging.FileHandler(f"logs/{self.log_file}")
        file_format = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        
        # Console handler  
        console_handler = logging.StreamHandler()
        console_format = logging.Formatter(
            '%(asctime)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
    async def _on_market_data(self, market_data: MarketData):
        """Handle incoming market data from real feeds"""
        await self._process_market_data(market_data)
        
    async def _process_market_data(self, market_data: MarketData):
        """Process market data and update positions"""
        try:
            # Store price history
            price_record = {
                'timestamp': market_data.timestamp,
                'symbol': market_data.symbol,
                'open': market_data.open,
                'high': market_data.high,
                'low': market_data.low,
                'close': market_data.close,
                'volume': market_data.volume,
                'bid': market_data.bid or market_data.close - 0.25,
                'ask': market_data.ask or market_data.close + 0.25
            }
            
            self.price_history.append(price_record)
            
            # Maintain history size
            if len(self.price_history) > self.max_history_length:
                self.price_history = self.price_history[-self.max_history_length:]
                
            # Update positions
            self._update_positions(market_data)
            
            # Check for trading signals
            await self._check_trading_signals(market_data)
            
            # Log periodic updates
            self._log_market_update(market_data)
            
        except Exception as e:
            self.logger.error(f"Error processing market data: {e}")
            
    def _update_positions(self, market_data: MarketData):
        """Update all positions with current market price"""
        symbol = market_data.symbol
        current_price = market_data.close
        
        if symbol in self.positions:
            # Update position and get P&L change
            pnl_change = self.positions[symbol].update_price(current_price)
            
            # Update account equity
            old_equity = self.equity
            self.unrealized_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
            self.equity = self.current_balance + self.unrealized_pnl
            
            # Track drawdown
            if self.equity > self.peak_equity:
                self.peak_equity = self.equity
                
            current_drawdown = (self.peak_equity - self.equity) / self.peak_equity
            self.max_drawdown = max(self.max_drawdown, current_drawdown)
            
            # Check exit conditions synchronously
            self._check_exit_conditions_sync(symbol, market_data)
            
    def _check_exit_conditions_sync(self, symbol: str, market_data: MarketData):
        """Check if position should be closed due to stop loss or take profit"""
        if symbol not in self.positions:
            return
            
        position = self.positions[symbol]
        current_price = market_data.close
        
        should_exit = False
        exit_reason = None
        exit_price = None
        
        # Check stop loss
        if position.stop_loss:
            if (position.quantity > 0 and current_price <= position.stop_loss) or \
               (position.quantity < 0 and current_price >= position.stop_loss):
                should_exit = True
                exit_reason = "STOP_LOSS"
                exit_price = position.stop_loss
                
        # Check take profit
        if position.take_profit and not should_exit:
            if (position.quantity > 0 and current_price >= position.take_profit) or \
               (position.quantity < 0 and current_price <= position.take_profit):
                should_exit = True
                exit_reason = "TAKE_PROFIT"
                exit_price = position.take_profit
                
        if should_exit:
            # Schedule async close for next iteration
            asyncio.create_task(self._close_position(symbol, exit_price, exit_reason))
            
    async def _check_exit_conditions(self, symbol: str, market_data: MarketData):
        """Async version for direct calls"""
        if symbol not in self.positions:
            return
            
        position = self.positions[symbol]
        current_price = market_data.close
        
        should_exit = False
        exit_reason = None
        exit_price = None
        
        # Check stop loss
        if position.stop_loss:
            if (position.quantity > 0 and current_price <= position.stop_loss) or \
               (position.quantity < 0 and current_price >= position.stop_loss):
                should_exit = True
                exit_reason = "STOP_LOSS"
                exit_price = position.stop_loss
                
        # Check take profit
        if position.take_profit and not should_exit:
            if (position.quantity > 0 and current_price >= position.take_profit) or \
               (position.quantity < 0 and current_price <= position.take_profit):
                should_exit = True
                exit_reason = "TAKE_PROFIT"
                exit_price = position.take_profit
                
        if should_exit:
            await self._close_position(symbol, exit_price, exit_reason)
            
    async def _check_trading_signals(self, market_data: MarketData):
        """Check for new trading opportunities"""
        # Rate limiting
        now = datetime.now()
        if self.last_signal_check and \
           (now - self.last_signal_check).total_seconds() < self.signal_check_interval:
            return
            
        self.last_signal_check = now
        
        # Need sufficient price history
        if len(self.price_history) < 50:
            return
            
        # Only trade during US market hours
        if not self._is_market_hours():
            return
            
        try:
            # Get strategy signal
            signal = await self._get_strategy_signal(market_data)
            
            if signal:
                await self._execute_signal(signal, market_data)
                
        except Exception as e:
            self.logger.error(f"Error checking trading signals: {e}")
            
    def _is_market_hours(self) -> bool:
        """Check if current time is within US trading hours"""
        now = datetime.now()
        # US regular hours: 9:30 AM - 4:00 PM EST (14:30 - 21:00 GMT)
        start_time = now.replace(hour=14, minute=30, second=0, microsecond=0)
        end_time = now.replace(hour=21, minute=0, second=0, microsecond=0)
        
        return start_time <= now <= end_time
        
    async def _get_strategy_signal(self, market_data: MarketData) -> Optional[Dict]:
        """Get trading signal from strategy"""
        try:
            # Convert price history to DataFrame
            df = pd.DataFrame(self.price_history[-200:])  # Last 200 ticks
            df.set_index('timestamp', inplace=True)
            
            # Calculate technical indicators
            df['sma_fast'] = df['close'].rolling(window=10).mean()
            df['sma_slow'] = df['close'].rolling(window=30).mean()
            df['rsi'] = self._calculate_rsi(df['close'], window=14)
            
            # Get latest values
            latest = df.iloc[-1]
            previous = df.iloc[-2]
            
            # Simple momentum strategy signals
            signal = None
            
            # Buy signal: Fast SMA crosses above slow SMA and RSI < 70
            if (latest['sma_fast'] > latest['sma_slow'] and 
                previous['sma_fast'] <= previous['sma_slow'] and 
                latest['rsi'] < 70):
                signal = {
                    'action': 'BUY',
                    'symbol': market_data.symbol,
                    'confidence': 0.7,
                    'stop_loss': market_data.close - 20.0,  # $20 stop
                    'take_profit': market_data.close + 40.0  # $40 target
                }
                
            # Sell signal: Fast SMA crosses below slow SMA and RSI > 30
            elif (latest['sma_fast'] < latest['sma_slow'] and 
                  previous['sma_fast'] >= previous['sma_slow'] and 
                  latest['rsi'] > 30):
                signal = {
                    'action': 'SELL',
                    'symbol': market_data.symbol,
                    'confidence': 0.7,
                    'stop_loss': market_data.close + 20.0,  # $20 stop
                    'take_profit': market_data.close - 40.0  # $40 target
                }
                
            return signal
            
        except Exception as e:
            self.logger.error(f"Strategy signal error: {e}")
            return None
            
    def _calculate_rsi(self, prices: pd.Series, window: int = 14) -> pd.Series:
        """Calculate Relative Strength Index"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
        
    async def _execute_signal(self, signal: Dict, market_data: MarketData):
        """Execute trading signal"""
        symbol = signal['symbol']
        action = signal['action']
        
        # Check if we already have a position
        if symbol in self.positions:
            # Close existing position first if opposite signal
            existing_pos = self.positions[symbol]
            if (action == 'BUY' and existing_pos.quantity < 0) or \
               (action == 'SELL' and existing_pos.quantity > 0):
                await self._close_position(symbol, market_data.close, "SIGNAL_REVERSAL")
            else:
                return  # Don't add to existing position in same direction
                
        # Check risk limits
        if not self._check_risk_limits():
            self.logger.warning("Risk limits exceeded - skipping trade")
            return
            
        # Calculate position size
        position_size = self._calculate_position_size(signal, market_data)
        
        if position_size > 0:
            if action == 'BUY':
                await self._open_position('BUY', symbol, position_size, 
                                        market_data.ask or market_data.close + 0.25,
                                        signal.get('stop_loss'), signal.get('take_profit'))
            elif action == 'SELL':
                await self._open_position('SELL', symbol, position_size,
                                        market_data.bid or market_data.close - 0.25,
                                        signal.get('stop_loss'), signal.get('take_profit'))
                                        
    def _calculate_position_size(self, signal: Dict, market_data: MarketData) -> int:
        """Calculate appropriate position size"""
        # Risk 1% of equity per trade
        risk_amount = self.equity * 0.01
        
        # Calculate stop loss distance
        entry_price = market_data.close
        stop_loss = signal.get('stop_loss', entry_price - 20.0)  # Default $20 stop
        stop_distance = abs(entry_price - stop_loss)
        
        # Position size = Risk Amount / Stop Distance
        position_size = int(risk_amount / stop_distance)
        
        # Ensure minimum size and maximum size limits
        position_size = max(1, min(position_size, 10))  # 1-10 contracts max
        
        return position_size
        
    async def _open_position(self, action: str, symbol: str, quantity: int, 
                           price: float, stop_loss: Optional[float] = None,
                           take_profit: Optional[float] = None):
        """Open new trading position"""
        try:
            # Calculate quantity with direction
            signed_quantity = quantity if action == 'BUY' else -quantity
            
            # Calculate costs
            notional_value = quantity * price
            commission = self._calculate_commission(quantity, price)
            
            # Check available margin
            if notional_value + commission > self.current_balance:
                self.logger.warning("Insufficient balance for trade")
                return
                
            # Create position
            position = Position(
                symbol=symbol,
                quantity=signed_quantity,
                entry_price=price,
                current_price=price,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            
            self.positions[symbol] = position
            
            # Create trade record
            trade_id = f"T{self.trade_counter:06d}"
            self.trade_counter += 1
            
            trade = PaperTrade(
                trade_id=trade_id,
                timestamp=datetime.now(),
                symbol=symbol,
                action=action,
                quantity=quantity,
                price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                commission=commission
            )
            
            self.trades.append(trade)
            
            # Update account
            self.current_balance -= commission
            self.session_trades += 1
            
            # Log trade
            direction = "🟢" if action == 'BUY' else "🔴"
            self.logger.info(f"{direction} {action} {quantity} {symbol} @ {price:.2f} | "
                           f"Stop: {stop_loss:.2f} | Target: {take_profit:.2f} | "
                           f"Balance: ${self.current_balance:.2f}")
            
        except Exception as e:
            self.logger.error(f"Error opening position: {e}")
            
    async def _close_position(self, symbol: str, exit_price: float, reason: str):
        """Close existing position"""
        try:
            if symbol not in self.positions:
                return
                
            position = self.positions[symbol]
            
            # Calculate P&L
            if position.quantity > 0:  # Long position
                gross_pnl = (exit_price - position.entry_price) * abs(position.quantity)
            else:  # Short position  
                gross_pnl = (position.entry_price - exit_price) * abs(position.quantity)
                
            commission = self._calculate_commission(abs(position.quantity), exit_price)
            net_pnl = gross_pnl - commission
            
            # Update trade record
            for trade in reversed(self.trades):
                if (trade.symbol == symbol and trade.status == "OPEN"):
                    trade.exit_price = exit_price
                    trade.exit_timestamp = datetime.now()
                    trade.pnl = net_pnl
                    trade.status = "CLOSED"
                    break
                    
            # Update account
            self.current_balance += (abs(position.quantity) * exit_price - commission)
            self.realized_pnl += net_pnl
            
            if net_pnl > 0:
                self.winning_trades += 1
                
            # Remove position
            del self.positions[symbol]
            
            # Log trade
            pnl_indicator = "💰" if net_pnl > 0 else "💸"
            self.logger.info(f"{pnl_indicator} CLOSE {symbol} @ {exit_price:.2f} | "
                           f"Reason: {reason} | P&L: ${net_pnl:.2f} | "
                           f"Balance: ${self.current_balance:.2f}")
            
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
            
    def _calculate_commission(self, quantity: int, price: float) -> float:
        """Calculate trading commission"""
        # NQ futures: $2.50 per side per contract
        return quantity * 2.50
        
    def _check_risk_limits(self) -> bool:
        """Check FTMO risk management rules"""
        current_loss = self.initial_balance - self.equity
        
        # Daily loss limit (5%)
        daily_limit = self.initial_balance * 0.05
        if current_loss >= daily_limit:
            self.logger.warning("🚨 FTMO Daily loss limit reached!")
            return False
            
        # Maximum loss limit (10%)  
        max_limit = self.initial_balance * 0.10
        if current_loss >= max_limit:
            self.logger.warning("🚨 FTMO Maximum loss limit reached!")
            return False
            
        return True
        
    def _log_market_update(self, market_data: MarketData):
        """Log periodic market updates"""
        # Log every 2 minutes
        now = datetime.now()
        if now.second % 120 == 0:  # Every 2 minutes
            
            position_info = ""
            if market_data.symbol in self.positions:
                pos = self.positions[market_data.symbol]
                position_info = (f"| Pos: {pos.quantity} @ {pos.entry_price:.2f} "
                               f"| P&L: ${pos.unrealized_pnl:.2f}")
                               
            self.logger.info(f"📊 {market_data.symbol}: ${market_data.close:.2f} "
                           f"| Equity: ${self.equity:.2f} {position_info}")
                           
    async def start_paper_trading(self, 
                                symbol: str = "NQ", 
                                duration_minutes: Optional[int] = None):
        """Start paper trading session"""
        
        self.start_time = datetime.now()
        self.is_running = True
        
        self.logger.info("🚀 Enhanced Paper Trading Started")
        self.logger.info("=" * 50)
        self.logger.info(f"Symbol: {symbol}")
        self.logger.info(f"Initial Balance: ${self.initial_balance:,.2f}")
        self.logger.info(f"Data Source: {'Real Market Data' if self.enable_real_data else 'Simulated'}")
        if duration_minutes:
            self.logger.info(f"Duration: {duration_minutes} minutes")
        self.logger.info("Press Ctrl+C to stop")
        self.logger.info("=" * 50)
        
        try:
            if self.enable_real_data:
                # Use real data feed
                feed_task = asyncio.create_task(
                    self.data_provider.start_feed(symbol, update_interval=5)
                )
                
                if duration_minutes:
                    await asyncio.sleep(duration_minutes * 60)
                    self.data_provider.stop_feed()
                else:
                    await feed_task
                    
            else:
                # Use simulated data
                await self._run_simulated_trading(symbol, duration_minutes)
                
        except KeyboardInterrupt:
            self.logger.info("Trading stopped by user")
        except Exception as e:
            self.logger.error(f"Trading error: {e}")
        finally:
            self.is_running = False
            self._print_session_summary()
            
    async def _run_simulated_trading(self, symbol: str, duration_minutes: Optional[int]):
        """Run trading with simulated data"""
        end_time = None
        if duration_minutes:
            end_time = datetime.now() + timedelta(minutes=duration_minutes)
            
        update_interval = 5  # seconds
        
        while self.is_running:
            if end_time and datetime.now() >= end_time:
                break
                
            # Generate simulated market data
            market_data = self.data_provider.generate_tick(symbol)
            
            # Process the data
            await self._process_market_data(market_data)
            
            await asyncio.sleep(update_interval)
            
    def _print_session_summary(self):
        """Print final trading session summary"""
        if not self.start_time:
            return
            
        runtime = datetime.now() - self.start_time
        runtime_hours = runtime.total_seconds() / 3600
        
        # Calculate performance metrics
        total_return = ((self.equity - self.initial_balance) / self.initial_balance) * 100
        win_rate = (self.winning_trades / max(1, self.session_trades)) * 100
        avg_trade_pnl = self.realized_pnl / max(1, self.session_trades)
        
        # FTMO compliance
        current_loss = max(0, self.initial_balance - self.equity)
        daily_loss_pct = (current_loss / self.initial_balance) * 100
        max_loss_pct = daily_loss_pct
        
        print("\n" + "=" * 60)
        print("📈 ENHANCED PAPER TRADING SESSION SUMMARY")
        print("=" * 60)
        print(f"Session Duration: {runtime_hours:.2f} hours")
        print(f"Initial Balance: ${self.initial_balance:,.2f}")
        print(f"Final Equity: ${self.equity:,.2f}")
        print(f"Total Return: {total_return:+.2f}%")
        print(f"Realized P&L: ${self.realized_pnl:,.2f}")
        print(f"Unrealized P&L: ${self.unrealized_pnl:,.2f}")
        print(f"Max Drawdown: {self.max_drawdown*100:.2f}%")
        print(f"")
        print(f"Trading Statistics:")
        print(f"  Total Trades: {self.session_trades}")
        print(f"  Winning Trades: {self.winning_trades}")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Average Trade P&L: ${avg_trade_pnl:.2f}")
        print(f"")
        print(f"FTMO Compliance:")
        print(f"  Daily Loss: {daily_loss_pct:.2f}% (Limit: 5.0%)")
        print(f"  Max Loss: {max_loss_pct:.2f}% (Limit: 10.0%)")
        
        # Overall assessment
        ftmo_passed = daily_loss_pct < 5.0 and max_loss_pct < 10.0
        profit_target = total_return >= 8.0  # FTMO £50k target is typically 8%
        
        print(f"")
        if ftmo_passed and profit_target:
            print("🎉 FTMO EVALUATION: WOULD PASS")
        elif ftmo_passed:
            print("⚠️  FTMO EVALUATION: Risk limits OK, need more profit")
        else:
            print("❌ FTMO EVALUATION: WOULD FAIL (Risk limits exceeded)")
        print("=" * 60)


# Convenience function for quick testing
async def quick_test(duration_minutes: int = 30, real_data: bool = True):
    """Quick test function for paper trading"""
    engine = EnhancedPaperTradingEngine(
        initial_balance=50000.0,
        enable_real_data=real_data
    )
    
    await engine.start_paper_trading("NQ", duration_minutes=duration_minutes)


if __name__ == "__main__":
    print("🎯 Enhanced Paper Trading Engine")
    print("Real-time paper trading with market data integration")
    print()
    
    # Show setup instructions
    if not REAL_DATA_AVAILABLE:
        print("📋 Setup Instructions for Real Data:")
        print("1. pip install aiohttp websockets yfinance")
        print("2. Set environment variables (optional):")
        print("   - ALPHA_VANTAGE_API_KEY")
        print("   - TWELVE_DATA_API_KEY")
        print()
    
    print("🚀 Starting 1-hour paper trading session...")
    print("Press Ctrl+C to stop early")
    print()
    
    # Run paper trading
    asyncio.run(quick_test(duration_minutes=60, real_data=REAL_DATA_AVAILABLE))
