#!/usr/bin/env python3
"""
Enhanced FTMO Challenge Simulation - Using Proven Strategy Parameters
This simulation uses our validated optimization results and realistic trade execution.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import logging
import warnings
import json
warnings.filterwarnings('ignore')

@dataclass
class FTMOChallengeConfig:
    """FTMO Challenge Configuration"""
    account_size: float = 50000.0  # £50k
    profit_target_pct: float = 10.0  # 10% for challenge
    daily_loss_limit_pct: float = 5.0  # 5% daily loss limit
    total_loss_limit_pct: float = 10.0  # 10% total loss limit
    min_trading_days: int = 4  # Minimum 4 trading days

@dataclass
class FTMOVerificationConfig:
    """FTMO Verification Configuration"""
    account_size: float = 50000.0  # £50k
    profit_target_pct: float = 5.0  # 5% for verification
    daily_loss_limit_pct: float = 5.0  # 5% daily loss limit
    total_loss_limit_pct: float = 10.0  # 10% total loss limit
    min_trading_days: int = 4  # Minimum 4 trading days

@dataclass
class ChallengeResult:
    """Results from a single FTMO challenge or verification"""
    passed: bool
    final_pnl: float
    final_pnl_pct: float
    max_daily_loss: float
    max_daily_loss_pct: float
    max_drawdown: float
    max_drawdown_pct: float
    trading_days: int
    total_trades: int
    win_rate: float
    profit_factor: float
    reason_failed: Optional[str] = None

class ProvenAtlasStrategy:
    """Atlas Momentum Strategy using proven optimization parameters"""
    
    def __init__(self):
        # Proven "Momentum Master" parameters from final optimization
        self.strategy_stats = {
            'annual_return': 0.1152,  # 11.52%
            'win_rate': 0.458,        # 45.8%
            'profit_factor': 2.03,
            'max_drawdown': 0.0218,   # 2.18%
            'sharpe_ratio': 4.18,
            'avg_trades_per_month': 33  # From backtest
        }
        
        # Trade outcome distributions (from our optimization)
        self.avg_win_amount = 580
        self.avg_loss_amount = 285
        self.max_position_size = 2.0  # Max 2 contracts
        self.risk_per_trade = 0.012   # 1.2% risk per trade
        
    def generate_monthly_trades(self, month_index: int, market_volatility: float = 1.0) -> List[Dict]:
        """Generate realistic trades for a month based on proven statistics"""
        
        # Adjust number of trades based on market conditions
        base_trades = self.strategy_stats['avg_trades_per_month']
        num_trades = max(20, int(base_trades * market_volatility * np.random.uniform(0.8, 1.2)))
        
        trades = []
        current_date = datetime(2023, month_index + 1, 1)
        
        # Generate trades spread across trading days
        trading_days = 22  # Average trading days per month
        trades_per_day = num_trades / trading_days
        
        for day in range(trading_days):
            # Number of trades this day (Poisson distribution)
            daily_trades = np.random.poisson(trades_per_day)
            
            for trade_num in range(daily_trades):
                # Trade outcome based on proven win rate
                is_winner = np.random.random() < self.strategy_stats['win_rate']
                
                if is_winner:
                    # Winning trade - use proven distribution
                    pnl = np.random.lognormal(np.log(self.avg_win_amount), 0.3)
                else:
                    # Losing trade - more consistent losses
                    pnl = -np.random.normal(self.avg_loss_amount, 50)
                
                # Apply position sizing and risk management
                position_size = min(self.max_position_size, np.random.uniform(0.5, 2.0))
                
                # Scale PnL by position size
                scaled_pnl = pnl * position_size
                
                # Add slippage and commission
                scaled_pnl -= position_size * 2.0  # £2 per contract
                
                # Trade timestamp
                trade_time = current_date + timedelta(days=day, hours=np.random.randint(14, 20))
                
                trades.append({
                    'timestamp': trade_time,
                    'pnl': scaled_pnl,
                    'position_size': position_size,
                    'is_winner': is_winner,
                    'day': day
                })
        
        return sorted(trades, key=lambda x: x['timestamp'])

class EnhancedFTMOSimulator:
    """Enhanced FTMO simulator using proven strategy statistics"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.setup_logging()
        
        self.strategy = ProvenAtlasStrategy()
        self.challenge_config = FTMOChallengeConfig()
        self.verification_config = FTMOVerificationConfig()
        
    def setup_logging(self):
        """Setup logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    def simulate_monthly_challenge(self, month_index: int, config: FTMOChallengeConfig, phase_name: str = "Challenge") -> ChallengeResult:
        """Simulate a monthly FTMO challenge using proven strategy performance"""
        
        # Generate market volatility for this month (affects trade frequency)
        market_volatility = np.random.uniform(0.8, 1.3)
        
        # Generate trades for the month
        trades = self.strategy.generate_monthly_trades(month_index, market_volatility)
        
        if not trades:
            return ChallengeResult(
                passed=False,
                final_pnl=-config.account_size,
                final_pnl_pct=-100.0,
                max_daily_loss=config.account_size,
                max_daily_loss_pct=100.0,
                max_drawdown=config.account_size,
                max_drawdown_pct=100.0,
                trading_days=0,
                total_trades=0,
                win_rate=0.0,
                profit_factor=0.0,
                reason_failed="No trades generated"
            )
        
        # Simulate trading the month
        account_balance = config.account_size
        daily_pnl_map = {}
        equity_curve = [account_balance]
        max_drawdown = 0.0
        max_daily_loss = 0.0
        
        # Risk limits
        daily_loss_limit = config.account_size * (config.daily_loss_limit_pct / 100)
        total_loss_limit = config.account_size * (config.total_loss_limit_pct / 100)
        profit_target = config.account_size * (config.profit_target_pct / 100)
        
        # Process trades day by day
        for trade in trades:
            day = trade['day']
            
            # Initialize daily P&L if new day
            if day not in daily_pnl_map:
                daily_pnl_map[day] = 0.0
            
            # Execute trade
            trade_pnl = trade['pnl']
            account_balance += trade_pnl
            daily_pnl_map[day] += trade_pnl
            equity_curve.append(account_balance)
            
            # Check daily loss limit
            if daily_pnl_map[day] < -daily_loss_limit:
                return ChallengeResult(
                    passed=False,
                    final_pnl=account_balance - config.account_size,
                    final_pnl_pct=(account_balance - config.account_size) / config.account_size * 100,
                    max_daily_loss=abs(daily_pnl_map[day]),
                    max_daily_loss_pct=abs(daily_pnl_map[day]) / config.account_size * 100,
                    max_drawdown=max_drawdown,
                    max_drawdown_pct=max_drawdown / config.account_size * 100,
                    trading_days=len(daily_pnl_map),
                    total_trades=len(trades),
                    win_rate=0.0,
                    profit_factor=0.0,
                    reason_failed=f"Daily loss limit exceeded: £{abs(daily_pnl_map[day]):.2f} > £{daily_loss_limit:.2f}"
                )
            
            # Update drawdown
            peak = max(equity_curve)
            current_drawdown = peak - account_balance
            max_drawdown = max(max_drawdown, current_drawdown)
            
            # Check total loss limit
            total_loss = config.account_size - account_balance
            if total_loss > total_loss_limit:
                return ChallengeResult(
                    passed=False,
                    final_pnl=account_balance - config.account_size,
                    final_pnl_pct=(account_balance - config.account_size) / config.account_size * 100,
                    max_daily_loss=max_daily_loss,
                    max_daily_loss_pct=max_daily_loss / config.account_size * 100,
                    max_drawdown=max_drawdown,
                    max_drawdown_pct=max_drawdown / config.account_size * 100,
                    trading_days=len(daily_pnl_map),
                    total_trades=len(trades),
                    win_rate=0.0,
                    profit_factor=0.0,
                    reason_failed=f"Total loss limit exceeded: £{total_loss:.2f} > £{total_loss_limit:.2f}"
                )
            
            # Check profit target
            total_profit = account_balance - config.account_size
            if total_profit >= profit_target:
                # Challenge passed!
                break
        
        # Calculate final metrics
        max_daily_loss = max(abs(pnl) for pnl in daily_pnl_map.values() if pnl < 0) if any(pnl < 0 for pnl in daily_pnl_map.values()) else 0
        final_pnl = account_balance - config.account_size
        final_pnl_pct = final_pnl / config.account_size * 100
        
        # Calculate trade statistics
        winning_trades = [t for t in trades if t['is_winner']]
        losing_trades = [t for t in trades if not t['is_winner']]
        
        win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
        
        total_wins = sum(t['pnl'] for t in winning_trades)
        total_losses = abs(sum(t['pnl'] for t in losing_trades))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        # Check if challenge passed
        passed = (
            final_pnl >= profit_target and
            len(daily_pnl_map) >= config.min_trading_days and
            max_daily_loss <= daily_loss_limit and
            max_drawdown <= total_loss_limit
        )
        
        # Determine failure reason
        reason_failed = None
        if not passed:
            if final_pnl < profit_target:
                reason_failed = f"Profit target not met: £{final_pnl:.2f} < £{profit_target:.2f}"
            elif len(daily_pnl_map) < config.min_trading_days:
                reason_failed = f"Insufficient trading days: {len(daily_pnl_map)} < {config.min_trading_days}"
            elif max_daily_loss > daily_loss_limit:
                reason_failed = f"Daily loss limit exceeded: £{max_daily_loss:.2f} > £{daily_loss_limit:.2f}"
            elif max_drawdown > total_loss_limit:
                reason_failed = f"Total loss limit exceeded: £{max_drawdown:.2f} > £{total_loss_limit:.2f}"
        
        return ChallengeResult(
            passed=passed,
            final_pnl=final_pnl,
            final_pnl_pct=final_pnl_pct,
            max_daily_loss=max_daily_loss,
            max_daily_loss_pct=max_daily_loss / config.account_size * 100,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown / config.account_size * 100,
            trading_days=len(daily_pnl_map),
            total_trades=len(trades),
            win_rate=win_rate,
            profit_factor=profit_factor,
            reason_failed=reason_failed
        )
    
    def run_12_month_simulation(self) -> Dict:
        """Run 12-month FTMO simulation"""
        
        print("🏆 Enhanced FTMO Challenge Simulation")
        print("Using Proven Atlas Momentum Strategy Parameters")
        print("=" * 60)
        
        challenge_results = []
        verification_results = []
        monthly_summaries = []
        
        for month in range(12):
            print(f"\n📅 MONTH {month + 1}: {datetime(2023, month + 1, 1).strftime('%B %Y')}")
            print("-" * 50)
            
            # Run FTMO Challenge
            print("🔥 Running FTMO Challenge...")
            challenge_result = self.simulate_monthly_challenge(month, self.challenge_config, "Challenge")
            challenge_results.append(challenge_result)
            
            challenge_status = "✅ PASSED" if challenge_result.passed else "❌ FAILED"
            print(f"   Result: {challenge_status}")
            print(f"   Final P&L: £{challenge_result.final_pnl:.2f} ({challenge_result.final_pnl_pct:.2f}%)")
            print(f"   Max Daily Loss: £{challenge_result.max_daily_loss:.2f}")
            print(f"   Max Drawdown: £{challenge_result.max_drawdown:.2f}")
            print(f"   Trading Days: {challenge_result.trading_days}")
            print(f"   Total Trades: {challenge_result.total_trades}")
            print(f"   Win Rate: {challenge_result.win_rate:.1f}%")
            
            if not challenge_result.passed:
                print(f"   Failure Reason: {challenge_result.reason_failed}")
            
            # If challenge passed, run verification
            verification_result = None
            if challenge_result.passed:
                print("🏆 Running FTMO Verification...")
                verification_result = self.simulate_monthly_challenge(month, self.verification_config, "Verification")
                verification_results.append(verification_result)
                
                verification_status = "✅ PASSED" if verification_result.passed else "❌ FAILED"
                print(f"   Result: {verification_status}")
                print(f"   Final P&L: £{verification_result.final_pnl:.2f} ({verification_result.final_pnl_pct:.2f}%)")
                
                if not verification_result.passed:
                    print(f"   Failure Reason: {verification_result.reason_failed}")
            else:
                verification_results.append(None)
            
            # Overall result
            overall_passed = challenge_result.passed and verification_result and verification_result.passed
            overall_status = "🎉 FUNDED" if overall_passed else "🔄 RETRY"
            print(f"   Overall: {overall_status}")
            
            monthly_summaries.append({
                'month': month + 1,
                'challenge_passed': challenge_result.passed,
                'verification_passed': verification_result.passed if verification_result else False,
                'overall_passed': overall_passed,
                'final_pnl': verification_result.final_pnl if verification_result and verification_result.passed else challenge_result.final_pnl
            })
        
        # Calculate statistics
        challenge_pass_rate = sum(1 for r in challenge_results if r.passed) / len(challenge_results) * 100
        verifications_attempted = len([r for r in verification_results if r])
        verification_pass_rate = sum(1 for r in verification_results if r and r.passed) / verifications_attempted * 100 if verifications_attempted > 0 else 0
        overall_pass_rate = sum(1 for s in monthly_summaries if s['overall_passed']) / len(monthly_summaries) * 100
        
        results = {
            'challenge_results': challenge_results,
            'verification_results': verification_results,
            'challenge_pass_rate': challenge_pass_rate,
            'verification_pass_rate': verification_pass_rate,
            'overall_pass_rate': overall_pass_rate,
            'monthly_summaries': monthly_summaries
        }
        
        self.print_final_summary(results)
        return results
    
    def print_final_summary(self, results: Dict):
        """Print comprehensive final summary"""
        print(f"\n{'='*80}")
        print("🏆 FTMO SIMULATION FINAL SUMMARY")
        print(f"{'='*80}")
        
        print(f"📊 OVERALL STATISTICS:")
        print(f"   Challenge Pass Rate: {results['challenge_pass_rate']:.1f}%")
        print(f"   Verification Pass Rate: {results['verification_pass_rate']:.1f}%")
        print(f"   Overall Success Rate: {results['overall_pass_rate']:.1f}%")
        
        print(f"\n📅 MONTHLY BREAKDOWN:")
        print(f"{'Month':<5} {'Challenge':<10} {'Verification':<12} {'Overall':<8} {'P&L':<10}")
        print("-" * 50)
        
        for summary in results['monthly_summaries']:
            month = summary['month']
            challenge = "✅ PASS" if summary['challenge_passed'] else "❌ FAIL"
            verification = "✅ PASS" if summary['verification_passed'] else "❌ FAIL" if summary['challenge_passed'] else "N/A"
            overall = "🎉 FUND" if summary['overall_passed'] else "🔄 RETRY"
            pnl = f"£{summary['final_pnl']:,.0f}"
            
            print(f"{month:<5} {challenge:<10} {verification:<12} {overall:<8} {pnl:<10}")
        
        # Performance analysis
        passed_challenges = [r for r in results['challenge_results'] if r.passed]
        if passed_challenges:
            avg_profit = np.mean([r.final_pnl for r in passed_challenges])
            avg_trades = np.mean([r.total_trades for r in passed_challenges])
            avg_win_rate = np.mean([r.win_rate for r in passed_challenges])
            
            print(f"\n📈 PERFORMANCE ANALYSIS:")
            print(f"   Average Profit (Passed Challenges): £{avg_profit:.2f}")
            print(f"   Average Trades per Month: {avg_trades:.1f}")
            print(f"   Average Win Rate: {avg_win_rate:.1f}%")
        
        # Strategy assessment
        print(f"\n🎯 STRATEGY ASSESSMENT:")
        if results['overall_pass_rate'] >= 70:
            print(f"   ✅ EXCELLENT: Strategy ready for FTMO deployment!")
            print(f"   Expected monthly success rate: {results['overall_pass_rate']:.1f}%")
        elif results['overall_pass_rate'] >= 50:
            print(f"   ⚠️  GOOD: Strategy shows solid performance")
            print(f"   Consider minor optimizations for higher success rate")
        elif results['overall_pass_rate'] >= 30:
            print(f"   🔄 MODERATE: Strategy needs improvement")
            print(f"   Recommend further optimization before live deployment")
        else:
            print(f"   ❌ POOR: Strategy requires significant changes")
            print(f"   Current parameters not suitable for FTMO")
        
        print(f"\n💡 RECOMMENDATIONS:")
        if results['overall_pass_rate'] >= 70:
            print(f"   • Deploy strategy with confidence")
            print(f"   • Monitor performance closely in first month")
            print(f"   • Consider scaling to multiple accounts")
        elif results['overall_pass_rate'] >= 50:
            print(f"   • Test strategy with smaller account size first")
            print(f"   • Review risk management parameters")
            print(f"   • Consider hybrid approach with fallback strategies")
        else:
            print(f"   • Significant strategy optimization required")
            print(f"   • Review fundamental strategy logic")
            print(f"   • Consider alternative trading approaches")
        
        print(f"\n{'='*80}")

def main():
    """Main execution function"""
    
    simulator = EnhancedFTMOSimulator()
    results = simulator.run_12_month_simulation()
    
    # Save results
    summary = {
        'simulation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'overall_pass_rate': float(results['overall_pass_rate']),
        'challenge_pass_rate': float(results['challenge_pass_rate']),
        'verification_pass_rate': float(results['verification_pass_rate']),
        'monthly_results': [
            {
                'month': int(s['month']),
                'challenge_passed': bool(s['challenge_passed']),
                'verification_passed': bool(s['verification_passed']),
                'overall_passed': bool(s['overall_passed']),
                'final_pnl': float(s['final_pnl'])
            }
            for s in results['monthly_summaries']
        ]
    }
    
    with open('enhanced_ftmo_simulation.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n📄 Detailed results saved to enhanced_ftmo_simulation.json")
    print(f"🎯 Overall FTMO Success Rate: {results['overall_pass_rate']:.1f}%")

if __name__ == "__main__":
    main()
