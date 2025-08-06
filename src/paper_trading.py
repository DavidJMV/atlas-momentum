"""
Paper Trading Engine for Atlas Strategy
Real-time paper trading with live market data
"""

import asyncio
import json
import logging
from datetime import datetime, time
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from dataclasses import dataclass, asdict

from config.config import config
from src.strategies.atlas_momentum import AtlasMomentumStrategy
from src.risk_management.risk_manager import FTMORiskManager
from src.risk_management.position_sizer import FTMOPositionSizer


@dataclass
class PaperTrade:
    """Paper trade record"""
    trade_id: str
    timestamp: datetime
    symbol: str
    side: str  # "BUY" or "SELL"
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    status: str  # "OPEN", "CLOSED", "CANCELLED"
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None
    pnl: Optional[float] = None
    commission: float = 0.0


@dataclass
class PaperAccount:
    """Paper trading account state"""
    balance: float
    equity: float
    unrealized_pnl: float
    realized_pnl: float
    margin_used: float
    free_margin: float
    daily_pnl: float
    trades_today: int
    total_trades: int


class RealTimeDataFeed:
    """
    Real-time data feed for paper trading
    Can be connected to various data providers
    """
    
    def __init__(self):
        self.subscribers = []
        self.current_prices = {}
        self.is_running = False
        
    def subscribe(self, callback):
        """Subscribe to price updates"""
        self.subscribers.append(callback)
        
    async def start_feed(self, symbol: str = "NQ"):
        """Start real-time data feed"""
        self.is_running = True
        
        # In production, connect to real data provider
        # For demo, simulate realistic NQ price movement
        await self._simulate_real_data(symbol)
        
    async def _simulate_real_data(self, symbol: str):
        """Simulate realistic market data for testing"""
        # Start with current NQ price approximation
        base_price = 15000.0
        
        while self.is_running:
            # Generate realistic price movement
            tick_change = np.random.normal(0, 2.5)  # 2.5 point std dev
            base_price += tick_change
            
            # Create tick data
            tick_data = {
                'symbol': symbol,
                'timestamp': datetime.now(),
                'bid': base_price - 0.25,
                'ask': base_price + 0.25,
                'last': base_price,
                'volume': np.random.randint(10, 100)
            }
            
            self.current_prices[symbol] = tick_data
            
            # Notify subscribers
            for callback in self.subscribers:
                try:
                    await callback(tick_data)
                except Exception as e:
                    logging.error(f"Error in data callback: {e}")
                    
            await asyncio.sleep(1)  # 1-second updates for demo
            
    def stop_feed(self):
        """Stop data feed"""
        self.is_running = False
        
    def get_current_price(self, symbol: str) -> Optional[Dict]:
        """Get current price for symbol"""
        return self.current_prices.get(symbol)


class PaperTradingEngine:
    """
    Paper trading engine with real-time data
    Simulates FTMO environment exactly
    """
    
    def __init__(self):
        # Initialize components
        self.data_feed = RealTimeDataFeed()
        self.risk_manager = FTMORiskManager()
        self.position_sizer = FTMOPositionSizer()
        
        # Account state
        self.account = PaperAccount(
            balance=config.ftmo.account_size,
            equity=config.ftmo.account_size,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            margin_used=0.0,
            free_margin=config.ftmo.account_size,
            daily_pnl=0.0,
            trades_today=0,
            total_trades=0
        )
        
        # Trading state
        self.open_trades: Dict[str, PaperTrade] = {}
        self.closed_trades: List[PaperTrade] = []
        self.is_trading = False
        self.current_day = None
        
        # Strategy state (simplified for demo)
        self.last_signal_time = None
        self.trades_today = 0
        
        # Logging
        self.logger = logging.getLogger(__name__)
        self.setup_logging()
        
        # Subscribe to price updates
        self.data_feed.subscribe(self.on_price_update)
        
    def setup_logging(self):
        """Setup logging for paper trading"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/paper_trading.log'),
                logging.StreamHandler()
            ]
        )
        
    async def start_paper_trading(self, symbol: str = "NQ"):
        """Start paper trading session"""
        self.logger.info("Starting paper trading session...")
        self.is_trading = True
        
        # Start data feed
        await asyncio.gather(
            self.data_feed.start_feed(symbol),
            self.trading_loop()
        )
        
    async def trading_loop(self):
        """Main trading loop"""
        while self.is_trading:
            try:
                current_time = datetime.now().time()
                
                # Check if in trading session
                if self.is_trading_session(current_time):
                    await self.process_trading_logic()
                else:
                    # Close positions outside trading hours
                    await self.close_all_positions("SESSION_END")
                    
                # Update daily counters
                self.update_daily_state()
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(1)
                
    def is_trading_session(self, current_time: time) -> bool:
        """Check if current time is within trading session"""
        session_start = time(14, 30)  # 14:30 GMT
        session_end = time(20, 0)     # 20:00 GMT
        return session_start <= current_time <= session_end
        
    async def process_trading_logic(self):
        """Process trading logic and signals"""
        # Get current market data
        price_data = self.data_feed.get_current_price("NQ")
        if not price_data:
            return
            
        # Manage existing positions
        await self.manage_open_positions(price_data)
        
        # Check for new signals (simplified logic for demo)
        if len(self.open_trades) == 0:  # No open positions
            signal = await self.generate_signal(price_data)
            if signal:
                await self.execute_signal(signal, price_data)
                
    async def generate_signal(self, price_data: Dict) -> Optional[Dict]:
        """Generate trading signal (simplified for demo)"""
        
        # Check trade limits
        if self.trades_today >= config.trading.max_trades_per_day:
            return None
            
        # Check gap between trades
        if (self.last_signal_time and 
            (datetime.now() - self.last_signal_time).total_seconds() < 3600):  # 1 hour
            return None
            
        # Simplified signal generation (in real implementation, use full strategy)
        # For demo, generate random signals with realistic probability
        if np.random.random() < 0.1:  # 10% chance per check
            signal_type = "LONG" if np.random.random() > 0.5 else "SHORT"
            
            current_price = price_data['last']
            atr_estimate = 25.0  # Estimated ATR for NQ
            
            if signal_type == "LONG":
                stop_loss = current_price - (2.5 * atr_estimate)
                take_profit = current_price + (1.8 * 2.5 * atr_estimate)
            else:
                stop_loss = current_price + (2.5 * atr_estimate)
                take_profit = current_price - (1.8 * 2.5 * atr_estimate)
                
            return {
                'type': signal_type,
                'entry_price': current_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'confidence': 0.7
            }
            
        return None
        
    async def execute_signal(self, signal: Dict, price_data: Dict):
        """Execute trading signal"""
        
        # Calculate position size
        entry_price = signal['entry_price']
        stop_loss = signal['stop_loss']
        
        position_size = self.position_sizer.calculate_size(
            entry_price=entry_price,
            stop_loss_price=stop_loss,
            current_equity=self.account.equity,
            realized_pnl=self.account.realized_pnl,
            current_drawdown=self.calculate_current_drawdown()
        )
        
        if position_size == 0:
            self.logger.info("Position size calculated as 0, skipping trade")
            return
            
        # Check risk limits
        if not self.risk_manager.can_open_trade(
            self.account.daily_pnl, 
            self.calculate_current_drawdown()
        ):
            self.logger.info("Risk manager rejected trade")
            return
            
        # Create trade
        trade_id = f"PAPER_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        trade = PaperTrade(
            trade_id=trade_id,
            timestamp=datetime.now(),
            symbol="NQ",
            side="BUY" if signal['type'] == "LONG" else "SELL",
            quantity=position_size,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=signal['take_profit'],
            status="OPEN",
            commission=config.broker.commission_per_lot
        )
        
        # Add to open trades
        self.open_trades[trade_id] = trade
        
        # Update account
        self.account.trades_today += 1
        self.account.total_trades += 1
        self.trades_today += 1
        self.last_signal_time = datetime.now()
        
        # Log trade
        self.logger.info(f"PAPER TRADE OPENED: {signal['type']} {position_size} NQ @ {entry_price:.2f}")
        self.logger.info(f"Stop Loss: {stop_loss:.2f}, Take Profit: {signal['take_profit']:.2f}")
        
    async def manage_open_positions(self, price_data: Dict):
        """Manage open positions"""
        current_price = price_data['last']
        trades_to_close = []
        
        for trade_id, trade in self.open_trades.items():
            # Calculate unrealized P&L
            if trade.side == "BUY":
                unrealized_pnl = (current_price - trade.entry_price) * trade.quantity
                
                # Check stop loss
                if current_price <= trade.stop_loss:
                    trades_to_close.append((trade_id, current_price, "STOP_LOSS"))
                # Check take profit
                elif current_price >= trade.take_profit:
                    trades_to_close.append((trade_id, current_price, "TAKE_PROFIT"))
                    
            else:  # SELL
                unrealized_pnl = (trade.entry_price - current_price) * trade.quantity
                
                # Check stop loss
                if current_price >= trade.stop_loss:
                    trades_to_close.append((trade_id, current_price, "STOP_LOSS"))
                # Check take profit
                elif current_price <= trade.take_profit:
                    trades_to_close.append((trade_id, current_price, "TAKE_PROFIT"))
                    
        # Close triggered trades
        for trade_id, exit_price, reason in trades_to_close:
            await self.close_trade(trade_id, exit_price, reason)
            
    async def close_trade(self, trade_id: str, exit_price: float, reason: str):
        """Close a specific trade"""
        if trade_id not in self.open_trades:
            return
            
        trade = self.open_trades[trade_id]
        
        # Calculate P&L
        if trade.side == "BUY":
            pnl = (exit_price - trade.entry_price) * trade.quantity
        else:
            pnl = (trade.entry_price - exit_price) * trade.quantity
            
        # Subtract commission
        pnl -= trade.commission
        
        # Update trade
        trade.exit_price = exit_price
        trade.exit_time = datetime.now()
        trade.exit_reason = reason
        trade.pnl = pnl
        trade.status = "CLOSED"
        
        # Update account
        self.account.realized_pnl += pnl
        self.account.daily_pnl += pnl
        self.account.equity = self.account.balance + self.account.realized_pnl
        
        # Move to closed trades
        self.closed_trades.append(trade)
        del self.open_trades[trade_id]
        
        # Log trade close
        self.logger.info(f"PAPER TRADE CLOSED: {trade.side} {trade.quantity} NQ")
        self.logger.info(f"Entry: {trade.entry_price:.2f}, Exit: {exit_price:.2f}")
        self.logger.info(f"P&L: £{pnl:.2f}, Reason: {reason}")
        
    async def close_all_positions(self, reason: str):
        """Close all open positions"""
        price_data = self.data_feed.get_current_price("NQ")
        if not price_data:
            return
            
        current_price = price_data['last']
        trades_to_close = list(self.open_trades.keys())
        
        for trade_id in trades_to_close:
            await self.close_trade(trade_id, current_price, reason)
            
    def calculate_current_drawdown(self) -> float:
        """Calculate current equity drawdown"""
        peak_equity = max(config.ftmo.account_size, self.account.equity)
        if peak_equity <= 0:
            return 0.0
        return (peak_equity - self.account.equity) / config.ftmo.account_size
        
    def update_daily_state(self):
        """Update daily state tracking"""
        current_date = datetime.now().date()
        
        if self.current_day != current_date:
            # New day - reset daily counters
            self.current_day = current_date
            self.account.daily_pnl = 0.0
            self.account.trades_today = 0
            self.trades_today = 0
            self.logger.info(f"New trading day: {current_date}")
            
    def stop_trading(self):
        """Stop paper trading"""
        self.is_trading = False
        self.data_feed.stop_feed()
        self.logger.info("Paper trading stopped")
        
    def get_account_summary(self) -> Dict:
        """Get current account summary"""
        return {
            'account': asdict(self.account),
            'open_trades': len(self.open_trades),
            'total_trades': len(self.closed_trades),
            'current_drawdown': self.calculate_current_drawdown(),
            'risk_limits': {
                'daily_loss_limit': config.ftmo.max_daily_loss,
                'total_loss_limit': config.ftmo.max_total_loss,
                'daily_loss_remaining': config.ftmo.max_daily_loss + self.account.daily_pnl,
                'total_loss_remaining': config.ftmo.max_total_loss - abs(min(0, self.account.realized_pnl))
            }
        }
        
    def get_trade_history(self) -> List[Dict]:
        """Get trade history"""
        return [asdict(trade) for trade in self.closed_trades]
        
    async def on_price_update(self, price_data: Dict):
        """Handle price update"""
        # Update unrealized P&L for open positions
        total_unrealized = 0.0
        current_price = price_data['last']
        
        for trade in self.open_trades.values():
            if trade.side == "BUY":
                unrealized = (current_price - trade.entry_price) * trade.quantity
            else:
                unrealized = (trade.entry_price - current_price) * trade.quantity
            total_unrealized += unrealized
            
        self.account.unrealized_pnl = total_unrealized
        self.account.equity = self.account.balance + self.account.realized_pnl + self.account.unrealized_pnl


async def run_paper_trading_session():
    """Run a paper trading session"""
    
    print("🎯 ATLAS PAPER TRADING SESSION")
    print("=" * 50)
    print("Starting real-time paper trading with simulated market data...")
    print("Press Ctrl+C to stop")
    
    engine = PaperTradingEngine()
    
    try:
        # Run for a limited time or until interrupted
        await engine.start_paper_trading("NQ")
        
    except KeyboardInterrupt:
        print("\n🛑 Paper trading interrupted by user")
        
    finally:
        engine.stop_trading()
        
        # Print final results
        print("\n" + "=" * 50)
        print("PAPER TRADING SESSION RESULTS")
        print("=" * 50)
        
        summary = engine.get_account_summary()
        account = summary['account']
        
        print(f"Final Balance: £{account['balance']:,.2f}")
        print(f"Realized P&L: £{account['realized_pnl']:,.2f}")
        print(f"Unrealized P&L: £{account['unrealized_pnl']:,.2f}")
        print(f"Total Equity: £{account['equity']:,.2f}")
        print(f"Daily P&L: £{account['daily_pnl']:,.2f}")
        print(f"Total Trades: {account['total_trades']}")
        print(f"Open Positions: {summary['open_trades']}")
        print(f"Current Drawdown: {summary['current_drawdown']:.2%}")
        
        # Trade history
        trades = engine.get_trade_history()
        if trades:
            print(f"\nTrade History ({len(trades)} trades):")
            for trade in trades[-5:]:  # Show last 5 trades
                pnl_str = f"£{trade['pnl']:+.2f}" if trade['pnl'] else "Open"
                print(f"  {trade['timestamp'][:19]} | {trade['side']} {trade['quantity']} @ {trade['entry_price']:.2f} | {pnl_str}")


if __name__ == "__main__":
    # Run paper trading
    asyncio.run(run_paper_trading_session())
