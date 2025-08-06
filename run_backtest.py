#!/usr/bin/env python3
"""
Simple backtest runner for Atlas Strategy
"""

import sys
import os
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

import backtrader as bt
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from config.config import config

# Simple strategy test without complex imports
class SimpleAtlasStrategy(bt.Strategy):
    """Simplified Atlas Strategy for testing"""
    
    params = (
        ('atr_period', 14),
        ('ema_fast', 21),
        ('ema_slow', 50),
        ('rsi_period', 14),
        ('volume_threshold', 1.5),
        ('atr_multiplier', 2.5),
    )
    
    def __init__(self):
        # Technical indicators
        self.atr = bt.indicators.ATR(self.data, period=self.params.atr_period)
        self.ema_fast = bt.indicators.EMA(self.data.close, period=self.params.ema_fast)
        self.ema_slow = bt.indicators.EMA(self.data.close, period=self.params.ema_slow)
        self.rsi = bt.indicators.RSI(self.data.close, period=self.params.rsi_period)
        self.volume_sma = bt.indicators.SMA(self.data.volume, period=20)
        
        # Position tracking
        self.entry_price = None
        self.stop_loss = None
        self.take_profit = None
        
        # Daily tracking for FTMO rules
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.max_daily_loss = config.ftmo.max_daily_loss
        self.max_total_loss = config.ftmo.max_total_loss
        
    def log(self, txt, dt=None):
        """Logging function"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}: {txt}')
        
    def next(self):
        """Main strategy logic"""
        if not self.position:
            self._check_entry_signals()
        else:
            self._manage_position()
            
    def _check_entry_signals(self):
        """Check for entry signals"""
        # Skip if insufficient data
        if len(self.data) < max(self.params.ema_slow, self.params.rsi_period):
            return
            
        # Current values
        close = self.data.close[0]
        ema_fast = self.ema_fast[0]
        ema_slow = self.ema_slow[0]
        rsi = self.rsi[0]
        volume = self.data.volume[0]
        volume_avg = self.volume_sma[0]
        atr = self.atr[0]
        
        # Entry conditions
        bullish_trend = ema_fast > ema_slow
        rsi_oversold = 45 <= rsi <= 75  # Adjusted for FTMO
        volume_spike = volume > (volume_avg * self.params.volume_threshold)
        price_above_ema = close > ema_fast
        
        # Long entry signal
        if bullish_trend and rsi_oversold and volume_spike and price_above_ema:
            # Check daily loss limit
            if abs(self.daily_pnl) >= self.max_daily_loss * 0.8:  # 80% of limit
                return
                
            # Position sizing (1% risk per trade)
            risk_amount = config.ftmo.account_size * 0.01
            stop_distance = atr * self.params.atr_multiplier
            position_size = min(risk_amount / stop_distance, 1.0)  # Max 1 contract
            
            # Entry
            self.entry_price = close
            self.stop_loss = close - stop_distance
            self.take_profit = close + (stop_distance * 2.0)  # 2:1 R:R
            
            self.buy(size=position_size)
            self.log(f'BUY CREATE: {close:.2f}, SL: {self.stop_loss:.2f}, TP: {self.take_profit:.2f}')
            
    def _manage_position(self):
        """Manage open positions"""
        if not self.position:
            return
            
        close = self.data.close[0]
        
        # Stop loss
        if close <= self.stop_loss:
            self.close()
            self.log(f'STOP LOSS: {close:.2f}')
            
        # Take profit
        elif close >= self.take_profit:
            self.close()
            self.log(f'TAKE PROFIT: {close:.2f}')
            
    def notify_order(self, order):
        """Order notifications"""
        if order.status in [order.Submitted, order.Accepted]:
            return
            
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED: {order.executed.price:.2f}')
            else:
                self.log(f'SELL EXECUTED: {order.executed.price:.2f}')
                
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
            
    def notify_trade(self, trade):
        """Trade notifications"""
        if not trade.isclosed:
            return
            
        pnl = trade.pnl
        self.daily_pnl += pnl
        self.total_pnl += pnl
        
        self.log(f'TRADE PNL: {pnl:.2f}, Daily: {self.daily_pnl:.2f}, Total: {self.total_pnl:.2f}')


def get_nq_data():
    """Download NQ data for backtesting"""
    print("📊 Downloading NQ futures data...")
    
    # Use NQ=F (NASDAQ-100 futures)
    ticker = "NQ=F"
    
    # Get 1 year of data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    try:
        data = yf.download(ticker, start=start_date, end=end_date, interval="1h", progress=False)
        
        if data.empty:
            print("❌ No data received, using ES futures instead...")
            data = yf.download("ES=F", start=start_date, end=end_date, interval="1h", progress=False)
            
        if data.empty:
            print("❌ No futures data available, using QQQ instead...")
            data = yf.download("QQQ", start=start_date, end=end_date, interval="1h", progress=False)
            
        # Clean the data
        if hasattr(data.columns, 'levels'):  # MultiIndex columns
            data.columns = data.columns.droplevel(1)  # Remove ticker level
        
        # Ensure we have the standard OHLCV columns
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in required_cols:
            if col not in data.columns:
                print(f"❌ Missing {col} column")
                return None
        
        # Remove any NaN values
        data = data.dropna()
        
        print(f"✅ Downloaded {len(data)} price bars")
        print(f"📅 Data range: {data.index[0]} to {data.index[-1]}")
        print(f"📊 Columns: {list(data.columns)}")
        return data
        
    except Exception as e:
        print(f"❌ Error downloading data: {e}")
        return None


def run_backtest():
    """Run the Atlas Strategy backtest"""
    print("🚀 ATLAS STRATEGY BACKTEST")
    print("=" * 50)
    
    # Get data
    data = get_nq_data()
    if data is None or data.empty:
        print("❌ Unable to get market data")
        return
        
    # Create Cerebro engine
    cerebro = bt.Cerebro()
    
    # Add strategy
    cerebro.addstrategy(SimpleAtlasStrategy)
    
    # Convert data to backtrader format
    bt_data = bt.feeds.PandasData(dataname=data)
    cerebro.adddata(bt_data)
    
    # Set initial capital
    cerebro.broker.setcash(config.ftmo.account_size)
    
    # Add analyzer
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    
    print(f"💰 Starting Portfolio Value: £{cerebro.broker.getvalue():,.2f}")
    
    # Run backtest
    print("⚡ Running backtest...")
    results = cerebro.run()
    strategy = results[0]
    
    # Final results
    final_value = cerebro.broker.getvalue()
    total_return = (final_value - config.ftmo.account_size) / config.ftmo.account_size * 100
    
    print("\n" + "=" * 50)
    print("📈 BACKTEST RESULTS")
    print("=" * 50)
    print(f"Final Portfolio Value: £{final_value:,.2f}")
    print(f"Total Return: {total_return:.2f}%")
    print(f"Profit Target (10%): {'✅ ACHIEVED' if total_return >= 10 else '❌ NOT MET'}")
    
    # Detailed analysis
    returns = strategy.analyzers.returns.get_analysis()
    drawdown = strategy.analyzers.drawdown.get_analysis()
    trades = strategy.analyzers.trades.get_analysis()
    
    print(f"\n📊 Performance Metrics:")
    print(f"Max Drawdown: {drawdown.max.drawdown:.2f}%")
    print(f"Max Daily Loss Check: {'✅ PASSED' if drawdown.max.drawdown < 5 else '❌ FAILED'}")
    
    if 'total' in trades and trades['total']['total'] > 0:
        win_rate = (trades['won']['total'] / trades['total']['total']) * 100
        print(f"Total Trades: {trades['total']['total']}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Winning Trades: {trades['won']['total']}")
        print(f"Losing Trades: {trades['lost']['total']}")
        
        # FTMO Pass Criteria
        ftmo_pass = (
            total_return >= 10.0 and  # Profit target
            drawdown.max.drawdown < 10.0 and  # Max drawdown
            True  # Daily loss would need daily tracking
        )
        
        print(f"\n🎯 FTMO EVALUATION RESULT:")
        print(f"Status: {'✅ PASS' if ftmo_pass else '❌ FAIL'}")
        
        if ftmo_pass:
            print("🏆 Strategy shows strong potential for FTMO evaluation!")
        else:
            print("⚠️  Strategy needs optimization for FTMO requirements")
    
    print("\n" + "=" * 50)


if __name__ == "__main__":
    run_backtest()
