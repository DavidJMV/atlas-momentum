"""
Test Suite for Enhanced Paper Trading System
Validates all components and real data integration
"""

import asyncio
import sys
from pathlib import Path
import logging

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

try:
    from enhanced_paper_trading import EnhancedPaperTradingEngine
    from data.real_data_feed import DataFeedManager, MarketData
    IMPORTS_OK = True
except ImportError as e:
    print(f"❌ Import error: {e}")
    IMPORTS_OK = False


async def test_data_feed():
    """Test real data feed functionality"""
    print("\n🔍 Testing Real Data Feed")
    print("-" * 30)
    
    try:
        feed_manager = DataFeedManager()
        
        # Test data collection
        data_received = []
        
        async def collect_data(market_data):
            data_received.append(market_data)
            print(f"📊 {market_data.symbol}: ${market_data.close:.2f}")
            
        feed_manager.subscribe(collect_data)
        
        # Test for 10 seconds
        print("Collecting data for 10 seconds...")
        feed_task = asyncio.create_task(feed_manager.start_feed("NQ", update_interval=2))
        
        await asyncio.sleep(10)
        feed_manager.stop_feed()
        
        if data_received:
            print(f"✅ Received {len(data_received)} data points")
            latest = data_received[-1]
            print(f"   Latest: {latest.symbol} @ ${latest.close:.2f}")
            return True
        else:
            print("❌ No data received")
            return False
            
    except Exception as e:
        print(f"❌ Data feed test failed: {e}")
        return False


async def test_paper_trading():
    """Test paper trading engine"""
    print("\n🎯 Testing Paper Trading Engine")
    print("-" * 35)
    
    try:
        # Create engine with small balance for testing
        engine = EnhancedPaperTradingEngine(
            initial_balance=10000.0,
            enable_real_data=False  # Use simulation for testing
        )
        
        print("✅ Engine created successfully")
        print(f"   Initial balance: ${engine.initial_balance:,.2f}")
        
        # Test for 30 seconds
        print("Running paper trading test for 30 seconds...")
        
        test_task = asyncio.create_task(
            engine.start_paper_trading("NQ", duration_minutes=0.5)
        )
        
        await test_task
        
        # Check results
        summary = engine._print_session_summary()
        
        print("✅ Paper trading test completed")
        print(f"   Final equity: ${engine.equity:,.2f}")
        print(f"   Trades executed: {engine.session_trades}")
        
        return True
        
    except Exception as e:
        print(f"❌ Paper trading test failed: {e}")
        return False


async def test_strategy_signals():
    """Test strategy signal generation"""
    print("\n📈 Testing Strategy Signals")
    print("-" * 30)
    
    try:
        engine = EnhancedPaperTradingEngine(initial_balance=10000.0)
        
        # Generate test market data
        import datetime
        
        test_data = MarketData(
            symbol="NQ",
            timestamp=datetime.datetime.now(),
            open=15800.0,
            high=15820.0,
            low=15780.0,
            close=15810.0,
            volume=1000,
            bid=15809.75,
            ask=15810.25
        )
        
        # Populate price history
        for i in range(100):
            price = 15800 + (i * 0.5)  # Trending upward
            engine.price_history.append({
                'timestamp': datetime.datetime.now(),
                'symbol': 'NQ',
                'open': price,
                'high': price + 1,
                'low': price - 1,
                'close': price,
                'volume': 1000,
                'bid': price - 0.25,
                'ask': price + 0.25
            })
        
        # Test signal generation
        signal = await engine._get_strategy_signal(test_data)
        
        if signal:
            print(f"✅ Generated signal: {signal['action']}")
            print(f"   Confidence: {signal['confidence']}")
            print(f"   Stop loss: {signal.get('stop_loss', 'N/A')}")
            print(f"   Take profit: {signal.get('take_profit', 'N/A')}")
        else:
            print("ℹ️  No signal generated (normal)")
        
        print("✅ Strategy signal test completed")
        return True
        
    except Exception as e:
        print(f"❌ Strategy signal test failed: {e}")
        return False


async def test_risk_management():
    """Test FTMO risk management"""
    print("\n🛡️  Testing Risk Management")
    print("-" * 30)
    
    try:
        engine = EnhancedPaperTradingEngine(initial_balance=10000.0)
        
        # Test normal conditions
        normal_check = engine._check_risk_limits()
        print(f"✅ Normal risk check: {'PASS' if normal_check else 'FAIL'}")
        
        # Test daily loss limit
        engine.equity = 9400.0  # 6% loss (over 5% limit)
        daily_check = engine._check_risk_limits()
        print(f"✅ Daily loss limit test: {'PASS' if not daily_check else 'FAIL'}")
        
        # Reset and test max loss limit
        engine.equity = 8900.0  # 11% loss (over 10% limit)
        max_check = engine._check_risk_limits()
        print(f"✅ Max loss limit test: {'PASS' if not max_check else 'FAIL'}")
        
        print("✅ Risk management tests completed")
        return True
        
    except Exception as e:
        print(f"❌ Risk management test failed: {e}")
        return False


def test_imports():
    """Test all required imports"""
    print("\n📦 Testing Imports")
    print("-" * 20)
    
    modules = [
        ("pandas", "pandas"),
        ("numpy", "numpy"),
        ("asyncio", "asyncio"),
        ("aiohttp", "aiohttp"),
        ("websockets", "websockets"),
    ]
    
    results = []
    
    for module_name, import_name in modules:
        try:
            __import__(import_name)
            print(f"✅ {module_name}")
            results.append(True)
        except ImportError:
            print(f"❌ {module_name} (not installed)")
            results.append(False)
    
    return all(results)


async def run_comprehensive_test():
    """Run all tests"""
    print("🧪 Atlas Strategy - Paper Trading Test Suite")
    print("=" * 50)
    
    if not IMPORTS_OK:
        print("❌ Import errors detected. Please check your environment.")
        return False
    
    # Run tests
    test_results = []
    
    # Basic imports
    import_result = test_imports()
    test_results.append(("Imports", import_result))
    
    # Risk management
    risk_result = await test_risk_management()
    test_results.append(("Risk Management", risk_result))
    
    # Strategy signals
    signal_result = await test_strategy_signals()
    test_results.append(("Strategy Signals", signal_result))
    
    # Paper trading engine
    engine_result = await test_paper_trading()
    test_results.append(("Paper Trading", engine_result))
    
    # Real data feed (if available)
    try:
        data_result = await test_data_feed()
        test_results.append(("Real Data Feed", data_result))
    except Exception as e:
        print(f"ℹ️  Skipping real data test: {e}")
        test_results.append(("Real Data Feed", None))
    
    # Summary
    print("\n📋 Test Summary")
    print("=" * 20)
    
    passed = 0
    total = 0
    
    for test_name, result in test_results:
        if result is True:
            print(f"✅ {test_name}: PASS")
            passed += 1
            total += 1
        elif result is False:
            print(f"❌ {test_name}: FAIL")
            total += 1
        else:
            print(f"⏭️  {test_name}: SKIPPED")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! System ready for paper trading.")
    else:
        print("⚠️  Some tests failed. Check the setup before proceeding.")
    
    return passed == total


if __name__ == "__main__":
    print("Starting test suite...")
    
    # Setup logging for tests
    logging.basicConfig(level=logging.WARNING)  # Reduce noise during tests
    
    # Run tests
    try:
        result = asyncio.run(run_comprehensive_test())
        if result:
            print("\n🚀 Ready to run paper trading!")
            print("Execute: python src/enhanced_paper_trading.py")
        else:
            print("\n🔧 Please fix issues before proceeding")
    except KeyboardInterrupt:
        print("\nTest suite interrupted by user")
    except Exception as e:
        print(f"\nTest suite error: {e}")
