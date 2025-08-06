# Real Market Data Integration for Atlas Strategy

This document describes the real-time market data integration capabilities added to the Atlas Strategy paper trading system.

## 🎯 Overview

The enhanced paper trading system now supports real market data from multiple providers, allowing you to test the Atlas Strategy with live market conditions before deploying to FTMO evaluation.

## 📦 Components

### 1. Real Data Feed (`src/data/real_data_feed.py`)
- **Multiple Providers**: Alpha Vantage, Twelve Data, Yahoo Finance
- **Automatic Fallback**: Switches providers if one fails
- **Rate Limiting**: Respects API limits
- **WebSocket Support**: Real-time data streams

### 2. Enhanced Paper Trading (`src/enhanced_paper_trading.py`)
- **Real Data Integration**: Uses live market data when available
- **Simulation Fallback**: Works without API keys
- **FTMO Compliance**: Full risk management integration
- **Performance Tracking**: Detailed trade analytics

### 3. Setup Tools
- **`setup_real_data.py`**: Installs dependencies and creates API key template
- **`demo_paper_trading.py`**: Interactive demo system
- **`test_paper_trading.py`**: Comprehensive test suite

## 🚀 Quick Start

### 1. Install Dependencies
```bash
# Install all required packages
pip install -r requirements.txt

# Or run the setup script
python setup_real_data.py
```

### 2. Configure API Keys (Optional)
```bash
# Create .env file with your API keys
echo "ALPHA_VANTAGE_API_KEY=your_key_here" >> .env
echo "TWELVE_DATA_API_KEY=your_key_here" >> .env
```

**Free API Keys:**
- [Alpha Vantage](https://www.alphavantage.co/support/#api-key) - 5 calls/min, 500/day
- [Twelve Data](https://twelvedata.com/pricing) - 800 calls/day

### 3. Run Paper Trading
```bash
# Quick demo (5 minutes)
python demo_paper_trading.py

# Full enhanced paper trading
python src/enhanced_paper_trading.py

# Test data feeds
python src/data/real_data_feed.py
```

## 📊 Data Providers

### Primary Providers (With API Keys)

#### Alpha Vantage
- **Pros**: Reliable, good for intraday data
- **Cons**: 5 calls/minute limit on free tier
- **Best For**: Periodic updates, historical analysis

#### Twelve Data
- **Pros**: Higher daily limits, good WebSocket support
- **Cons**: Limited free tier features
- **Best For**: Real-time streaming, multiple symbols

### Fallback Provider (No API Key Required)

#### Yahoo Finance
- **Pros**: Free, no registration required
- **Cons**: Rate limited, less reliable
- **Best For**: Basic testing, backup data source

## 🎮 Usage Examples

### Basic Paper Trading
```python
from src.enhanced_paper_trading import EnhancedPaperTradingEngine

# Create engine
engine = EnhancedPaperTradingEngine(
    initial_balance=50000.0,
    enable_real_data=True
)

# Run for 1 hour
await engine.start_paper_trading("NQ", duration_minutes=60)
```

### Custom Data Feed
```python
from src.data.real_data_feed import DataFeedManager

# Create data manager
feed = DataFeedManager()

# Subscribe to updates
async def on_data(market_data):
    print(f"{market_data.symbol}: ${market_data.close:.2f}")

feed.subscribe(on_data)

# Start feed
await feed.start_feed("NQ", update_interval=5)
```

## 📈 Features

### Real-Time Data
- ✅ Live price feeds from multiple providers
- ✅ Automatic provider failover
- ✅ Rate limit management
- ✅ WebSocket support (where available)

### Paper Trading Engine
- ✅ FTMO-compliant risk management
- ✅ Real-time P&L tracking
- ✅ Automated stop loss/take profit
- ✅ Performance analytics
- ✅ Trade logging and reporting

### Strategy Integration
- ✅ Atlas Momentum Strategy implementation
- ✅ Technical indicator calculations
- ✅ Signal generation and execution
- ✅ Position sizing and risk management

## 🛡️ FTMO Compliance

The system enforces all FTMO rules:

### Daily Loss Limit (5%)
- Monitors real-time account equity
- Stops trading when limit approached
- Logs violations for review

### Maximum Loss Limit (10%)
- Tracks total drawdown from initial balance
- Emergency stop if limit reached
- Account protection mechanisms

### Trading Hours
- Respects US market hours (9:30 AM - 4:00 PM EST)
- Configurable time windows
- Automatic session management

## 📊 Performance Monitoring

### Real-Time Metrics
- Current balance and equity
- Unrealized and realized P&L
- Maximum drawdown tracking
- Win rate and trade statistics

### FTMO Evaluation Metrics
- Daily loss percentage
- Total loss percentage
- Profit target progress
- Risk limit compliance

### Trade Analytics
- Entry/exit prices and times
- Stop loss and take profit hits
- Commission and slippage tracking
- Signal performance analysis

## 🔧 Troubleshooting

### Common Issues

#### Import Errors
```bash
# Install missing dependencies
pip install aiohttp websockets yfinance

# Check Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```

#### API Rate Limits
- Use multiple API keys for higher limits
- Increase update intervals (5+ seconds)
- Enable automatic provider switching

#### Data Quality Issues
- Check internet connection
- Verify API key validity
- Use simulation mode for testing

### Debug Mode
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# More verbose output
engine = EnhancedPaperTradingEngine(enable_real_data=True)
```

## 🎯 Next Steps

### Before FTMO Evaluation
1. **Extended Paper Trading**: Run for several days to validate strategy
2. **Performance Analysis**: Review win rate, drawdown, and profit consistency
3. **Risk Validation**: Ensure FTMO limits are never exceeded
4. **Market Condition Testing**: Test in different volatility environments

### Optimization Options
1. **Strategy Parameters**: Fine-tune entry/exit signals
2. **Position Sizing**: Optimize risk per trade
3. **Time Filters**: Add market condition filters
4. **Multiple Timeframes**: Incorporate higher timeframe analysis

### Deployment Ready
- ✅ Real market data integration
- ✅ FTMO-compliant risk management
- ✅ Comprehensive testing suite
- ✅ Performance monitoring
- ✅ Automated trading logic

## 📞 Support

For issues or questions:

1. **Check Logs**: Review `logs/enhanced_paper_trading.log`
2. **Run Tests**: Execute `python test_paper_trading.py`
3. **Demo Mode**: Try `python demo_paper_trading.py`
4. **Documentation**: Review strategy documentation in `STRATEGY_ANALYSIS.md`

---

**⚠️ Important**: This is paper trading for testing purposes. Always validate thoroughly before live FTMO evaluation.
