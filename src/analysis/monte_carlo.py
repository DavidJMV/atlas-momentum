"""
Monte Carlo Analysis for FTMO Pass Probability
Simulates multiple evaluation scenarios to estimate success rates
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import random
from scipy import stats

from config.config import config


@dataclass
class SimulationResult:
    """Single simulation result"""
    final_balance: float
    max_drawdown: float
    total_trades: int
    win_rate: float
    profit_factor: float
    largest_loss: float
    largest_win: float
    passed_evaluation: bool
    failure_reason: Optional[str] = None


@dataclass
class MonteCarloResults:
    """Complete Monte Carlo analysis results"""
    total_simulations: int
    pass_rate: float
    median_final_balance: float
    percentile_25_balance: float
    percentile_75_balance: float
    worst_case_drawdown: float
    best_case_balance: float
    average_trades: int
    average_win_rate: float
    risk_of_ruin: float
    simulation_results: List[SimulationResult]


class FTMOMonteCarloSimulator:
    """
    Monte Carlo simulator for FTMO evaluation pass probability
    """
    
    def __init__(self, strategy_stats: Dict = None):
        """
        Initialize simulator with strategy statistics
        
        Args:
            strategy_stats: Historical strategy performance statistics
        """
        self.account_size = config.ftmo.account_size
        self.profit_target = config.ftmo.profit_target_pct * self.account_size
        self.max_daily_loss = config.ftmo.max_daily_loss
        self.max_total_loss = config.ftmo.max_total_loss
        self.evaluation_days = config.ftmo.evaluation_days
        
        # Default strategy statistics (can be overridden with backtest results)
        self.strategy_stats = strategy_stats or {
            'win_rate': 0.64,
            'avg_win': 45.0,
            'avg_loss': -25.0,
            'trade_frequency': 2.1,  # trades per day
            'win_std': 15.0,
            'loss_std': 8.0,
            'consecutive_losses_max': 5,
            'largest_single_loss': -180.0
        }
        
    def run_simulation(self, num_simulations: int = 1000, random_seed: int = None) -> MonteCarloResults:
        """
        Run Monte Carlo simulation
        
        Args:
            num_simulations: Number of simulation runs
            random_seed: Random seed for reproducibility
            
        Returns:
            MonteCarloResults: Complete simulation results
        """
        
        if random_seed:
            np.random.seed(random_seed)
            random.seed(random_seed)
            
        results = []
        
        for i in range(num_simulations):
            sim_result = self._simulate_single_evaluation()
            results.append(sim_result)
            
            if (i + 1) % 100 == 0:
                print(f"Completed {i + 1}/{num_simulations} simulations")
                
        return self._analyze_results(results)
    
    def _simulate_single_evaluation(self) -> SimulationResult:
        """
        Simulate a single 30-day FTMO evaluation
        
        Returns:
            SimulationResult: Result of single simulation
        """
        
        balance = self.account_size
        peak_balance = balance
        daily_pnl = 0.0
        total_trades = 0
        wins = 0
        losses = 0
        largest_win = 0.0
        largest_loss = 0.0
        consecutive_losses = 0
        max_consecutive_losses = 0
        
        # Daily simulation
        for day in range(self.evaluation_days):
            daily_pnl = 0.0
            daily_trades = self._generate_daily_trade_count()
            
            # Generate trades for the day
            for _ in range(daily_trades):
                trade_result = self._generate_trade_result()
                daily_pnl += trade_result
                total_trades += 1
                
                # Track wins/losses
                if trade_result > 0:
                    wins += 1
                    consecutive_losses = 0
                    largest_win = max(largest_win, trade_result)
                else:
                    losses += 1
                    consecutive_losses += 1
                    max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
                    largest_loss = min(largest_loss, trade_result)
                
                # Check daily loss limit during trading
                if daily_pnl <= -self.max_daily_loss:
                    return SimulationResult(
                        final_balance=balance + daily_pnl,
                        max_drawdown=(peak_balance - (balance + daily_pnl)) / self.account_size,
                        total_trades=total_trades,
                        win_rate=wins / total_trades if total_trades > 0 else 0,
                        profit_factor=self._calculate_profit_factor(wins, losses, largest_win, abs(largest_loss)),
                        largest_loss=largest_loss,
                        largest_win=largest_win,
                        passed_evaluation=False,
                        failure_reason="Daily loss limit exceeded"
                    )
            
            # Update balance
            balance += daily_pnl
            peak_balance = max(peak_balance, balance)
            
            # Check total loss limit
            total_drawdown = (self.account_size - balance) / self.account_size
            if total_drawdown >= config.ftmo.max_total_loss_pct:
                return SimulationResult(
                    final_balance=balance,
                    max_drawdown=total_drawdown,
                    total_trades=total_trades,
                    win_rate=wins / total_trades if total_trades > 0 else 0,
                    profit_factor=self._calculate_profit_factor(wins, losses, largest_win, abs(largest_loss)),
                    largest_loss=largest_loss,
                    largest_win=largest_win,
                    passed_evaluation=False,
                    failure_reason="Total loss limit exceeded"
                )
                
            # Check if profit target reached
            if balance >= (self.account_size + self.profit_target):
                break
        
        # Evaluation completed - check if passed
        final_profit = balance - self.account_size
        passed = final_profit >= self.profit_target
        max_dd = (peak_balance - balance) / self.account_size if balance < peak_balance else 0.0
        
        return SimulationResult(
            final_balance=balance,
            max_drawdown=max_dd,
            total_trades=total_trades,
            win_rate=wins / total_trades if total_trades > 0 else 0,
            profit_factor=self._calculate_profit_factor(wins, losses, largest_win, abs(largest_loss)),
            largest_loss=largest_loss,
            largest_win=largest_win,
            passed_evaluation=passed,
            failure_reason=None if passed else "Insufficient profit"
        )
    
    def _generate_daily_trade_count(self) -> int:
        """Generate number of trades for a day"""
        # Poisson distribution around average frequency
        avg_trades = self.strategy_stats['trade_frequency']
        return max(0, np.random.poisson(avg_trades))
    
    def _generate_trade_result(self) -> float:
        """
        Generate a single trade result based on strategy statistics
        
        Returns:
            float: Trade P/L
        """
        
        # Determine if trade is win or loss
        is_win = np.random.random() < self.strategy_stats['win_rate']
        
        if is_win:
            # Generate winning trade
            avg_win = self.strategy_stats['avg_win']
            win_std = self.strategy_stats['win_std']
            trade_result = np.random.normal(avg_win, win_std)
            return max(5.0, trade_result)  # Minimum win of £5
        else:
            # Generate losing trade
            avg_loss = self.strategy_stats['avg_loss']
            loss_std = self.strategy_stats['loss_std']
            trade_result = np.random.normal(avg_loss, loss_std)
            
            # Ensure loss doesn't exceed maximum single trade loss
            max_loss = min(self.strategy_stats['largest_single_loss'], -config.ftmo.max_trade_risk)
            return max(max_loss, min(-1.0, trade_result))  # Minimum loss of £1
    
    def _calculate_profit_factor(self, wins: int, losses: int, largest_win: float, largest_loss: float) -> float:
        """Calculate profit factor"""
        if losses == 0 or largest_loss == 0:
            return float('inf') if wins > 0 else 0.0
            
        total_wins = wins * (largest_win / wins if wins > 0 else 0)
        total_losses = losses * (largest_loss / losses if losses > 0 else 0)
        
        if total_losses == 0:
            return float('inf')
            
        return abs(total_wins / total_losses)
    
    def _analyze_results(self, results: List[SimulationResult]) -> MonteCarloResults:
        """
        Analyze simulation results and calculate statistics
        
        Args:
            results: List of simulation results
            
        Returns:
            MonteCarloResults: Analyzed results
        """
        
        passed_count = sum(1 for r in results if r.passed_evaluation)
        pass_rate = passed_count / len(results)
        
        balances = [r.final_balance for r in results]
        drawdowns = [r.max_drawdown for r in results]
        trade_counts = [r.total_trades for r in results]
        win_rates = [r.win_rate for r in results]
        
        return MonteCarloResults(
            total_simulations=len(results),
            pass_rate=pass_rate,
            median_final_balance=np.median(balances),
            percentile_25_balance=np.percentile(balances, 25),
            percentile_75_balance=np.percentile(balances, 75),
            worst_case_drawdown=max(drawdowns),
            best_case_balance=max(balances),
            average_trades=np.mean(trade_counts),
            average_win_rate=np.mean(win_rates),
            risk_of_ruin=sum(1 for r in results if r.max_drawdown >= 0.10) / len(results),
            simulation_results=results
        )
    
    def generate_report(self, results: MonteCarloResults) -> str:
        """
        Generate detailed analysis report
        
        Args:
            results: Monte Carlo results
            
        Returns:
            str: Formatted report
        """
        
        report = f"""
# FTMO Monte Carlo Analysis Report

## Summary Statistics
- **Total Simulations**: {results.total_simulations:,}
- **Pass Rate**: {results.pass_rate:.1%}
- **Risk of Ruin**: {results.risk_of_ruin:.1%}

## Balance Distribution
- **Median Final Balance**: £{results.median_final_balance:,.2f}
- **25th Percentile**: £{results.percentile_25_balance:,.2f}
- **75th Percentile**: £{results.percentile_75_balance:,.2f}
- **Best Case**: £{results.best_case_balance:,.2f}

## Risk Metrics
- **Worst Drawdown**: {results.worst_case_drawdown:.1%}
- **Average Trades**: {results.average_trades:.1f}
- **Average Win Rate**: {results.average_win_rate:.1%}

## Failure Analysis
"""
        
        # Analyze failure reasons
        failures = [r for r in results.simulation_results if not r.passed_evaluation]
        if failures:
            failure_reasons = {}
            for failure in failures:
                reason = failure.failure_reason or "Unknown"
                failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
                
            report += "\n### Failure Breakdown:\n"
            for reason, count in failure_reasons.items():
                pct = (count / len(failures)) * 100
                report += f"- **{reason}**: {count} ({pct:.1f}%)\n"
        
        # Recommendations
        report += f"""

## Recommendations

### Risk Management
- Current pass rate: {results.pass_rate:.1%}
- Target pass rate: ≥70%
"""
        
        if results.pass_rate < 0.70:
            report += """
### Suggested Improvements:
1. **Reduce Position Size**: Scale down by 10-15% to lower risk
2. **Tighter Stop Losses**: Reduce ATR multiplier from 2.5 to 2.0
3. **Lower Trade Frequency**: Reduce from current level to improve quality
4. **Enhance Filters**: Add volatility regime filter for better entry timing
"""
        else:
            report += """
### Strategy is Optimal:
- Pass rate exceeds 70% target
- Risk profile is well-balanced
- Continue with current parameters
"""
        
        return report
    
    def plot_results(self, results: MonteCarloResults, save_path: str = None):
        """
        Create visualization plots for Monte Carlo results
        
        Args:
            results: Monte Carlo results
            save_path: Optional path to save plots
        """
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # Balance distribution
        balances = [r.final_balance for r in results.simulation_results]
        axes[0, 0].hist(balances, bins=50, alpha=0.7, color='blue', edgecolor='black')
        axes[0, 0].axvline(self.account_size + self.profit_target, color='green', linestyle='--', label='Target')
        axes[0, 0].axvline(self.account_size, color='red', linestyle='--', label='Break-even')
        axes[0, 0].set_xlabel('Final Balance (£)')
        axes[0, 0].set_ylabel('Frequency')
        axes[0, 0].set_title('Final Balance Distribution')
        axes[0, 0].legend()
        
        # Drawdown distribution
        drawdowns = [r.max_drawdown * 100 for r in results.simulation_results]
        axes[0, 1].hist(drawdowns, bins=50, alpha=0.7, color='red', edgecolor='black')
        axes[0, 1].axvline(10, color='red', linestyle='--', label='10% Limit')
        axes[0, 1].set_xlabel('Maximum Drawdown (%)')
        axes[0, 1].set_ylabel('Frequency')
        axes[0, 1].set_title('Maximum Drawdown Distribution')
        axes[0, 1].legend()
        
        # Pass rate by balance range
        balance_ranges = np.linspace(min(balances), max(balances), 20)
        pass_rates = []
        for i in range(len(balance_ranges) - 1):
            range_results = [r for r in results.simulation_results 
                           if balance_ranges[i] <= r.final_balance < balance_ranges[i+1]]
            if range_results:
                pass_rate = sum(1 for r in range_results if r.passed_evaluation) / len(range_results)
                pass_rates.append(pass_rate * 100)
            else:
                pass_rates.append(0)
                
        axes[1, 0].plot(balance_ranges[:-1], pass_rates, marker='o')
        axes[1, 0].set_xlabel('Final Balance (£)')
        axes[1, 0].set_ylabel('Pass Rate (%)')
        axes[1, 0].set_title('Pass Rate by Balance Range')
        axes[1, 0].grid(True, alpha=0.3)
        
        # Win rate vs Final balance scatter
        win_rates = [r.win_rate * 100 for r in results.simulation_results]
        colors = ['green' if r.passed_evaluation else 'red' for r in results.simulation_results]
        axes[1, 1].scatter(win_rates, balances, c=colors, alpha=0.6)
        axes[1, 1].set_xlabel('Win Rate (%)')
        axes[1, 1].set_ylabel('Final Balance (£)')
        axes[1, 1].set_title('Win Rate vs Final Balance')
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()
    
    def sensitivity_analysis(self, parameter_ranges: Dict) -> pd.DataFrame:
        """
        Perform sensitivity analysis on key parameters
        
        Args:
            parameter_ranges: Dictionary of parameter ranges to test
            
        Returns:
            pd.DataFrame: Sensitivity analysis results
        """
        
        results = []
        base_stats = self.strategy_stats.copy()
        
        for param, values in parameter_ranges.items():
            for value in values:
                # Update parameter
                test_stats = base_stats.copy()
                test_stats[param] = value
                
                # Run simulation with updated parameter
                temp_simulator = FTMOMonteCarloSimulator(test_stats)
                mc_results = temp_simulator.run_simulation(num_simulations=500)
                
                results.append({
                    'parameter': param,
                    'value': value,
                    'pass_rate': mc_results.pass_rate,
                    'median_balance': mc_results.median_final_balance,
                    'worst_drawdown': mc_results.worst_case_drawdown
                })
                
        return pd.DataFrame(results)


def run_complete_analysis() -> MonteCarloResults:
    """
    Run complete Monte Carlo analysis with default parameters
    
    Returns:
        MonteCarloResults: Complete analysis results
    """
    
    # Strategy statistics based on backtesting
    strategy_stats = {
        'win_rate': 0.64,  # 64% win rate
        'avg_win': 42.5,   # Average win £42.50
        'avg_loss': -23.8, # Average loss £23.80
        'trade_frequency': 2.1,  # 2.1 trades per day
        'win_std': 18.5,   # Standard deviation of wins
        'loss_std': 9.2,   # Standard deviation of losses
        'consecutive_losses_max': 6,
        'largest_single_loss': -185.0  # Largest single loss
    }
    
    simulator = FTMOMonteCarloSimulator(strategy_stats)
    results = simulator.run_simulation(num_simulations=1000, random_seed=42)
    
    # Generate report
    report = simulator.generate_report(results)
    print(report)
    
    # Create visualizations
    simulator.plot_results(results)
    
    return results


if __name__ == "__main__":
    # Run analysis
    results = run_complete_analysis()
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"monte_carlo_results_{timestamp}.txt", "w") as f:
        simulator = FTMOMonteCarloSimulator()
        f.write(simulator.generate_report(results))
