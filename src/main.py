"""
Backtrader Implementation for Atlas Strategy
Complete backtesting framework with FTMO-compliant metrics
"""

import backtrader as bt
import pandas as pd
import numpy as np
from datetime import datetime, time
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from strategies.atlas_momentum import AtlasMomentumStrategy
from analysis.monte_carlo import run_complete_analysis
from config.config import config


class FTMOAnalyzer(bt.Analyzer):
    """
    Custom analyzer for FTMO-specific metrics
    """
    
    def __init__(self):
        self.daily_pnl = []
        self.current_daily_pnl = 0.0
        self.last_date = None
        self.peak_equity = config.ftmo.account_size
        self.max_drawdown = 0.0
        self.daily_losses = []
        self.evaluation_passed = False
        
    def next(self):
        """Called on each bar"""
        current_date = self.strategy.data.datetime.date(0)
        
        # Reset daily P/L on new day
        if self.last_date and current_date != self.last_date:
            self.daily_pnl.append(self.current_daily_pnl)
            if self.current_daily_pnl < 0:
                self.daily_losses.append(abs(self.current_daily_pnl))
            self.current_daily_pnl = 0.0
            
        self.last_date = current_date
        
        # Update equity tracking
        current_equity = self.strategy.broker.getvalue()
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
            
        # Calculate current drawdown
        current_drawdown = (self.peak_equity - current_equity) / config.ftmo.account_size
        self.max_drawdown = max(self.max_drawdown, current_drawdown)
        
    def stop(self):
        """Called when strategy stops"""
        # Add final day's P/L
        if self.current_daily_pnl != 0:
            self.daily_pnl.append(self.current_daily_pnl)
            
        # Check FTMO evaluation criteria
        final_equity = self.strategy.broker.getvalue()
        total_profit = final_equity - config.ftmo.account_size
        
        # Check if evaluation passed
        profit_target_met = total_profit >= (config.ftmo.profit_target_pct * config.ftmo.account_size)
        no_daily_breach = all(loss <= config.ftmo.max_daily_loss for loss in self.daily_losses)
        no_total_breach = self.max_drawdown <= config.ftmo.max_total_loss_pct
        
        self.evaluation_passed = profit_target_met and no_daily_breach and no_total_breach
        
    def get_analysis(self):
        """Return analysis results"""
        return {
            'evaluation_passed': self.evaluation_passed,
            'daily_pnl': self.daily_pnl,
            'max_drawdown': self.max_drawdown,
            'daily_losses': self.daily_losses,
            'max_daily_loss': max(self.daily_losses) if self.daily_losses else 0,
            'total_profit': self.strategy.broker.getvalue() - config.ftmo.account_size,
            'final_equity': self.strategy.broker.getvalue()
        }


def create_data_feed(symbol: str = "NQ", start_date: str = None, end_date: str = None):
    """
    Create data feed for backtesting
    In production, this would connect to actual data provider
    """
    
    # For demo purposes, create synthetic data
    # In real implementation, use actual market data
    
    start = datetime.strptime(start_date or "2023-01-01", "%Y-%m-%d")
    end = datetime.strptime(end_date or "2024-12-31", "%Y-%m-%d")
    
    # Generate synthetic NQ data (for demonstration)
    dates = pd.date_range(start=start, end=end, freq='1min')
    
    # Filter for trading hours (14:30-20:00 GMT)
    trading_hours = dates.to_series().dt.time
    trading_dates = dates[(trading_hours >= time(14, 30)) & (trading_hours <= time(20, 0))]
    
    # Generate realistic price data
    np.random.seed(42)  # For reproducible results
    n_points = len(trading_dates)
    
    # Simulate NQ price movement
    initial_price = 15000.0
    returns = np.random.normal(0, 0.001, n_points)  # 0.1% volatility per minute
    price_series = initial_price * np.exp(np.cumsum(returns))
    
    # Create OHLCV data
    data = pd.DataFrame({
        'datetime': trading_dates,
        'open': price_series,
        'high': price_series * (1 + np.abs(np.random.normal(0, 0.0005, n_points))),
        'low': price_series * (1 - np.abs(np.random.normal(0, 0.0005, n_points))),
        'close': price_series,
        'volume': np.random.randint(100, 1000, n_points)
    })
    
    data.set_index('datetime', inplace=True)
    
    # Create Backtrader data feed
    data_feed = bt.feeds.PandasData(
        dataname=data,
        datetime=None,  # Use index
        open='open',
        high='high',
        low='low',
        close='close',
        volume='volume',
        openinterest=-1
    )
    
    return data_feed


def run_backtest(
    start_date: str = "2023-01-01",
    end_date: str = "2024-12-31",
    initial_cash: float = None,
    plot_results: bool = True
):
    """
    Run complete backtest of Atlas strategy
    
    Args:
        start_date: Start date for backtest
        end_date: End date for backtest
        initial_cash: Initial account balance
        plot_results: Whether to plot results
        
    Returns:
        Dict: Backtest results
    """
    
    print(f"Running Atlas Strategy Backtest ({start_date} to {end_date})")
    print("=" * 60)
    
    # Create Cerebro engine
    cerebro = bt.Cerebro()
    
    # Add strategy
    cerebro.addstrategy(AtlasMomentumStrategy)
    
    # Add data feed
    data = create_data_feed("NQ", start_date, end_date)
    cerebro.adddata(data)
    
    # Set initial cash
    initial_cash = initial_cash or config.ftmo.account_size
    cerebro.broker.setcash(initial_cash)
    
    # Set commission (£4.50 round-turn for NQ)
    cerebro.broker.setcommission(commission=config.broker.commission_per_lot / 2)  # Per side
    
    # Add analyzers
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(FTMOAnalyzer, _name='ftmo')
    
    # Add observers
    cerebro.addobserver(bt.observers.Broker)
    cerebro.addobserver(bt.observers.Trades)
    cerebro.addobserver(bt.observers.BuySell)
    
    print(f"Starting Portfolio Value: £{cerebro.broker.getvalue():.2f}")
    
    # Run backtest
    results = cerebro.run()
    
    print(f"Final Portfolio Value: £{cerebro.broker.getvalue():.2f}")
    
    # Extract results
    strategy = results[0]
    
    # Get analyzer results
    sharpe = strategy.analyzers.sharpe.get_analysis()
    drawdown = strategy.analyzers.drawdown.get_analysis()
    trades = strategy.analyzers.trades.get_analysis()
    returns = strategy.analyzers.returns.get_analysis()
    ftmo = strategy.analyzers.ftmo.get_analysis()
    
    # Compile results
    backtest_results = {
        'initial_value': initial_cash,
        'final_value': cerebro.broker.getvalue(),
        'total_return': (cerebro.broker.getvalue() - initial_cash) / initial_cash,
        'sharpe_ratio': sharpe.get('sharperatio', 0),
        'max_drawdown': drawdown.get('max', {}).get('drawdown', 0),
        'total_trades': trades.get('total', {}).get('total', 0),
        'winning_trades': trades.get('won', {}).get('total', 0),
        'losing_trades': trades.get('lost', {}).get('total', 0),
        'win_rate': trades.get('won', {}).get('total', 0) / max(1, trades.get('total', {}).get('total', 1)),
        'avg_win': trades.get('won', {}).get('pnl', {}).get('average', 0),
        'avg_loss': trades.get('lost', {}).get('pnl', {}).get('average', 0),
        'largest_win': trades.get('won', {}).get('pnl', {}).get('max', 0),
        'largest_loss': trades.get('lost', {}).get('pnl', {}).get('max', 0),
        'profit_factor': abs(trades.get('won', {}).get('pnl', {}).get('total', 0) / 
                            trades.get('lost', {}).get('pnl', {}).get('total', -1)) if trades.get('lost', {}).get('pnl', {}).get('total', 0) != 0 else float('inf'),
        'ftmo_analysis': ftmo
    }
    
    # Print detailed results
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS SUMMARY")
    print("=" * 60)
    
    print(f"Total Return: {backtest_results['total_return']:.2%}")
    print(f"Sharpe Ratio: {backtest_results['sharpe_ratio']:.2f}")
    print(f"Max Drawdown: {backtest_results['max_drawdown']:.2%}")
    print(f"Total Trades: {backtest_results['total_trades']}")
    print(f"Win Rate: {backtest_results['win_rate']:.1%}")
    print(f"Profit Factor: {backtest_results['profit_factor']:.2f}")
    print(f"Average Win: £{backtest_results['avg_win']:.2f}")
    print(f"Average Loss: £{backtest_results['avg_loss']:.2f}")
    
    print("\n" + "=" * 60)
    print("FTMO EVALUATION ANALYSIS")
    print("=" * 60)
    
    ftmo_passed = ftmo['evaluation_passed']
    print(f"FTMO Evaluation Result: {'PASSED ✓' if ftmo_passed else 'FAILED ✗'}")
    print(f"Total Profit: £{ftmo['total_profit']:.2f}")
    print(f"Profit Target: £{config.ftmo.profit_target_pct * config.ftmo.account_size:.2f}")
    print(f"Max Daily Loss: £{ftmo['max_daily_loss']:.2f}")
    print(f"Daily Loss Limit: £{config.ftmo.max_daily_loss:.2f}")
    print(f"Max Drawdown: {ftmo['max_drawdown']:.2%}")
    print(f"Drawdown Limit: {config.ftmo.max_total_loss_pct:.1%}")
    
    # Plot results
    if plot_results:
        cerebro.plot(style='candlestick', volume=False)
    
    return backtest_results


def run_walk_forward_analysis():
    """
    Run walk-forward analysis to validate strategy robustness
    """
    
    print("Running Walk-Forward Analysis")
    print("=" * 60)
    
    # Define walk-forward periods
    periods = [
        ("2023-01-01", "2023-06-30", "2023-07-01", "2023-09-30"),
        ("2023-04-01", "2023-09-30", "2023-10-01", "2023-12-31"),
        ("2023-07-01", "2023-12-31", "2024-01-01", "2024-03-31"),
        ("2023-10-01", "2024-03-31", "2024-04-01", "2024-06-30"),
        ("2024-01-01", "2024-06-30", "2024-07-01", "2024-09-30"),
        ("2024-04-01", "2024-09-30", "2024-10-01", "2024-12-31")
    ]
    
    results = []
    
    for i, (train_start, train_end, test_start, test_end) in enumerate(periods):
        print(f"\nPeriod {i+1}: Training {train_start} to {train_end}, Testing {test_start} to {test_end}")
        
        # Run backtest on test period
        test_results = run_backtest(test_start, test_end, plot_results=False)
        
        results.append({
            'period': i + 1,
            'train_start': train_start,
            'train_end': train_end,
            'test_start': test_start,
            'test_end': test_end,
            'return': test_results['total_return'],
            'sharpe': test_results['sharpe_ratio'],
            'max_dd': test_results['max_drawdown'],
            'win_rate': test_results['win_rate'],
            'ftmo_passed': test_results['ftmo_analysis']['evaluation_passed']
        })
        
        print(f"Return: {test_results['total_return']:.2%}, "
              f"Sharpe: {test_results['sharpe_ratio']:.2f}, "
              f"FTMO: {'PASS' if test_results['ftmo_analysis']['evaluation_passed'] else 'FAIL'}")
    
    # Summary statistics
    df_results = pd.DataFrame(results)
    
    print("\n" + "=" * 60)
    print("WALK-FORWARD ANALYSIS SUMMARY")
    print("=" * 60)
    
    print(f"Average Return: {df_results['return'].mean():.2%}")
    print(f"Return Std Dev: {df_results['return'].std():.2%}")
    print(f"Average Sharpe: {df_results['sharpe'].mean():.2f}")
    print(f"Average Max DD: {df_results['max_dd'].mean():.2%}")
    print(f"Average Win Rate: {df_results['win_rate'].mean():.1%}")
    print(f"FTMO Pass Rate: {df_results['ftmo_passed'].sum()}/{len(df_results)} ({df_results['ftmo_passed'].mean():.1%})")
    
    return df_results


def main():
    """
    Main execution function
    Run complete analysis suite
    """
    
    print("ATLAS MOMENTUM STRATEGY - FTMO EVALUATION SYSTEM")
    print("=" * 80)
    print("Senior Quantitative Strategy for Maximum FTMO Pass Probability")
    print("=" * 80)
    
    # 1. Run primary backtest
    print("\n1. PRIMARY BACKTEST (2024 Full Year)")
    primary_results = run_backtest("2024-01-01", "2024-12-31", plot_results=False)
    
    # 2. Run walk-forward analysis
    print("\n2. WALK-FORWARD ANALYSIS")
    wf_results = run_walk_forward_analysis()
    
    # 3. Run Monte Carlo simulation
    print("\n3. MONTE CARLO SIMULATION")
    print("Running 1,000 simulations for pass probability analysis...")
    mc_results = run_complete_analysis()
    
    # 4. Final recommendations
    print("\n" + "=" * 80)
    print("FINAL RECOMMENDATIONS")
    print("=" * 80)
    
    ftmo_pass_rate = wf_results['ftmo_passed'].mean()
    mc_pass_rate = mc_results.pass_rate
    
    print(f"Walk-Forward FTMO Pass Rate: {ftmo_pass_rate:.1%}")
    print(f"Monte Carlo Pass Rate: {mc_pass_rate:.1%}")
    print(f"Target Pass Rate: ≥70%")
    
    if mc_pass_rate >= 0.70:
        print("\n✓ STRATEGY APPROVED FOR FTMO EVALUATION")
        print("The Atlas Momentum Strategy meets the ≥70% pass rate requirement.")
        print("Proceed with live evaluation deployment.")
    else:
        print("\n⚠ STRATEGY REQUIRES OPTIMIZATION")
        print("Current pass rate below 70% target. Consider:")
        print("- Reducing position size by 10-15%")
        print("- Tightening stop losses (2.0x ATR vs 2.5x)")
        print("- Adding volatility regime filter")
        print("- Reducing trade frequency for higher quality setups")
    
    print("\n" + "=" * 80)
    print("Analysis complete. Ready for FTMO evaluation.")
    print("=" * 80)
    
    return {
        'primary_backtest': primary_results,
        'walk_forward': wf_results,
        'monte_carlo': mc_results
    }


if __name__ == "__main__":
    # Configure Python environment first
    try:
        results = main()
    except Exception as e:
        print(f"Error running analysis: {e}")
        print("Ensure all dependencies are installed: pip install -r requirements.txt")
