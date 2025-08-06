"""
Interactive Brokers Integration for Atlas Strategy
Connects to IB TWS API for real market data and paper trading
"""

import asyncio
import logging
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Callable
import pandas as pd
from dataclasses import dataclass

# IB API imports (install with: pip install ibapi)
try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    from ibapi.order import Order
    from ibapi.common import TickerId, OrderId
    import threading
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False
    print("⚠️ IB API not available. Install with: pip install ibapi")


@dataclass
class IBMarketData:
    """IB market data structure"""
    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    last: float
    volume: int
    bid_size: int = 0
    ask_size: int = 0


class IBTradingApp(EWrapper, EClient):
    """
    Interactive Brokers TWS connection for Atlas Strategy
    """
    
    def __init__(self):
        EClient.__init__(self, self)
        
        # Connection state
        self.connected = False
        self.next_order_id = None
        
        # Data storage
        self.market_data: Dict[int, IBMarketData] = {}
        self.positions: Dict[str, Dict] = {}
        self.account_info: Dict[str, str] = {}
        
        # Callbacks
        self.data_callbacks: List[Callable] = []
        self.connection_callbacks: List[Callable] = []
        
        # Request tracking
        self.req_id_counter = 1000
        self.contract_details: Dict[int, Contract] = {}
        
        # Historical data storage
        self.historical_data: Dict[int, List] = {}
        self.historical_data_complete: Dict[int, bool] = {}
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
    def get_next_req_id(self) -> int:
        """Get next unique request ID"""
        self.req_id_counter += 1
        return self.req_id_counter
        
    def subscribe_to_data(self, callback: Callable):
        """Subscribe to market data updates"""
        self.data_callbacks.append(callback)
        
    def subscribe_to_connection(self, callback: Callable):
        """Subscribe to connection status updates"""
        self.connection_callbacks.append(callback)
        
    # Connection callbacks
    def connectAck(self):
        """Connection acknowledged"""
        self.logger.info("✅ Connected to IB TWS")
        self.connected = True
        for callback in self.connection_callbacks:
            callback("connected")
            
    def connectionClosed(self):
        """Connection closed"""
        self.logger.info("❌ Disconnected from IB TWS")
        self.connected = False
        for callback in self.connection_callbacks:
            callback("disconnected")
            
    def error(self, reqId: TickerId, errorCode: int, errorString: str):
        """Error handling"""
        if errorCode in [2104, 2106, 2158]:  # Info messages
            self.logger.info(f"IB Info: {errorString}")
        elif errorCode in [502, 503, 504]:  # Connection errors
            self.logger.error(f"IB Connection Error: {errorString}")
        else:
            self.logger.error(f"IB Error {errorCode}: {errorString}")
            
    def nextValidId(self, orderId: OrderId):
        """Receive next valid order ID"""
        self.next_order_id = orderId
        self.logger.info(f"Next valid order ID: {orderId}")
        
    # Market data callbacks
    def tickPrice(self, reqId: TickerId, tickType: int, price: float, attrib):
        """Handle tick price updates"""
        if reqId not in self.market_data:
            self.market_data[reqId] = IBMarketData(
                symbol="",
                timestamp=datetime.now(),
                bid=0.0,
                ask=0.0,
                last=0.0,
                volume=0
            )
            
        data = self.market_data[reqId]
        data.timestamp = datetime.now()
        
        # Tick types: 1=bid, 2=ask, 4=last
        if tickType == 1:  # Bid
            data.bid = price
        elif tickType == 2:  # Ask
            data.ask = price
        elif tickType == 4:  # Last
            data.last = price
            
        # Notify subscribers
        for callback in self.data_callbacks:
            try:
                callback(reqId, data)
            except Exception as e:
                self.logger.error(f"Data callback error: {e}")
                
    def tickSize(self, reqId: TickerId, tickType: int, size: int):
        """Handle tick size updates"""
        if reqId in self.market_data:
            data = self.market_data[reqId]
            
            # Size types: 0=bid_size, 3=ask_size, 5=volume
            if tickType == 0:  # Bid size
                data.bid_size = size
            elif tickType == 3:  # Ask size
                data.ask_size = size
            elif tickType == 5:  # Volume
                data.volume = size
                
    def historicalData(self, reqId: int, bar):
        """Handle historical data bars"""
        if reqId not in self.historical_data:
            self.historical_data[reqId] = []
            
        # Convert IB bar to pandas-compatible format
        bar_data = {
            'datetime': pd.to_datetime(bar.date),
            'open': float(bar.open),
            'high': float(bar.high),
            'low': float(bar.low),
            'close': float(bar.close),
            'volume': int(bar.volume)
        }
        
        self.historical_data[reqId].append(bar_data)
        
    def historicalDataEnd(self, reqId: int, start: str, end: str):
        """Historical data request completed"""
        self.historical_data_complete[reqId] = True
        self.logger.info(f"Historical data complete for request {reqId}: {start} to {end}")
                
    # Account and position callbacks
    def updateAccountValue(self, key: str, val: str, currency: str, accountName: str):
        """Update account values"""
        if currency == "GBP" or currency == "BASE":  # Focus on GBP for FTMO
            self.account_info[key] = val
            
    def updatePortfolio(self, contract: Contract, position: float, 
                       marketPrice: float, marketValue: float,
                       averageCost: float, unrealizedPNL: float,
                       realizedPNL: float, accountName: str):
        """Update position information"""
        symbol = f"{contract.symbol}.{contract.exchange}"
        self.positions[symbol] = {
            'position': position,
            'market_price': marketPrice,
            'market_value': marketValue,
            'average_cost': averageCost,
            'unrealized_pnl': unrealizedPNL,
            'realized_pnl': realizedPNL
        }


class IBDataProvider:
    """
    Data provider using Interactive Brokers
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1):
        self.host = host
        self.port = port
        self.client_id = client_id
        
        self.app = IBTradingApp()
        self.connection_thread = None
        self.is_connected = False
        
        # Market data subscriptions
        self.subscriptions: Dict[str, int] = {}
        self.subscribers: List[Callable] = []
        
        # Historical data storage
        self.historical_data = {}
        self.historical_data_complete = {}
        
        self.logger = logging.getLogger(__name__)
        
    def subscribe(self, callback: Callable):
        """Subscribe to market data updates"""
        self.subscribers.append(callback)
        
    async def connect(self) -> bool:
        """Connect to IB TWS"""
        try:
            self.logger.info(f"Connecting to IB TWS at {self.host}:{self.port}")
            
            # Start connection in separate thread
            self.app.connect(self.host, self.port, self.client_id)
            
            # Start message processing thread
            self.connection_thread = threading.Thread(target=self.app.run, daemon=True)
            self.connection_thread.start()
            
            # Wait for connection
            for _ in range(50):  # 5 second timeout
                if self.app.connected:
                    self.is_connected = True
                    self.logger.info("✅ Connected to IB TWS")
                    return True
                await asyncio.sleep(0.1)
                
            self.logger.error("❌ Failed to connect to IB TWS")
            return False
            
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from IB TWS"""
        if self.is_connected:
            self.app.disconnect()
            self.is_connected = False
            
    def create_contract(self, symbol: str, sec_type: str = "STK", 
                       exchange: str = "SMART", currency: str = "GBP") -> Contract:
        """Create IB contract object"""
        contract = Contract()
        contract.symbol = symbol
        contract.secType = sec_type
        contract.exchange = exchange
        contract.currency = currency
        return contract
        
    def create_nq_contract(self) -> Contract:
        """Create NQ futures contract for Atlas Strategy - CME Real-Time L1"""
        contract = Contract()
        contract.symbol = "NQ"
        contract.secType = "FUT"
        contract.exchange = "CME"
        contract.currency = "USD"
        # Use continuous contract (no expiry needed for historical data)
        contract.lastTradeDateOrContractMonth = "202409"  # September 2025 contract
        return contract
        
    async def subscribe_to_market_data(self, symbol: str, contract_type: str = "STK"):
        """Subscribe to real-time market data"""
        if not self.is_connected:
            self.logger.error("Not connected to IB TWS")
            return False
            
        try:
            # Create contract
            if symbol == "NQ" and contract_type == "FUT":
                contract = self.create_nq_contract()
            else:
                contract = self.create_contract(symbol, contract_type)
                
            # Get request ID
            req_id = self.app.get_next_req_id()
            
            # Store subscription
            self.subscriptions[symbol] = req_id
            self.app.contract_details[req_id] = contract
            
            # Subscribe to market data callback
            def on_market_data(req_id: int, data: IBMarketData):
                if req_id == self.subscriptions.get(symbol):
                    # Convert to standard format and notify subscribers
                    market_data = {
                        'symbol': symbol,
                        'timestamp': data.timestamp,
                        'bid': data.bid,
                        'ask': data.ask,
                        'last': data.last,
                        'price': data.last if data.last > 0 else (data.bid + data.ask) / 2,
                        'volume': data.volume
                    }
                    
                    for callback in self.subscribers:
                        try:
                            callback(market_data)
                        except Exception as e:
                            self.logger.error(f"Subscriber callback error: {e}")
                            
            self.app.subscribe_to_data(on_market_data)
            
            # Request market data
            self.app.reqMktData(req_id, contract, "", False, False, [])
            
            self.logger.info(f"✅ Subscribed to {symbol} market data")
            return True
            
        except Exception as e:
            self.logger.error(f"Market data subscription error: {e}")
            return False
            
    def get_account_info(self) -> Dict[str, str]:
        """Get current account information"""
        if self.is_connected:
            self.app.reqAccountUpdates(True, "")
            return self.app.account_info
        return {}
        
    def get_positions(self) -> Dict[str, Dict]:
        """Get current positions"""
        if self.is_connected:
            return self.app.positions
        return {}
        
    def get_historical_data(self, symbol: str, exchange: str = "SMART", 
                           start_time: datetime = None, end_time: datetime = None,
                           bar_size: str = "1 min", duration: str = "1 D") -> Optional[pd.DataFrame]:
        """Get historical data from IB"""
        if not self.is_connected:
            self.logger.error("Not connected to IB TWS")
            return None
            
        try:
            # Create contract
            if symbol == "NQ" and exchange == "CME":
                contract = self.create_nq_contract()
            else:
                contract = self.create_contract(symbol, "STK", exchange)
                
            # Get request ID
            req_id = self.app.get_next_req_id()
            
            # Format end time (IB format: YYYYMMDD HH:MM:SS TMZ)
            if end_time is None:
                end_time = datetime.now()
            end_time_str = end_time.strftime("%Y%m%d %H:%M:%S GMT")
            
            # Calculate duration if start_time provided
            if start_time:
                duration_seconds = (end_time - start_time).total_seconds()
                if duration_seconds < 3600:  # Less than 1 hour
                    duration = f"{int(duration_seconds)} S"
                elif duration_seconds < 86400:  # Less than 1 day
                    duration = f"{int(duration_seconds/3600)} H"
                else:  # Days
                    duration = f"{int(duration_seconds/86400)} D"
            
            # Ensure proper duration format for IB API
            if not any(duration.endswith(unit) for unit in ['S', 'H', 'D', 'W', 'M', 'Y']):
                duration = "2 H"  # Default to 2 hours
            
            self.logger.info(f"Requesting historical data: {symbol} {duration} {bar_size}")
            
            # Initialize storage for this request
            self.app.historical_data[req_id] = []
            self.app.historical_data_complete[req_id] = False
            
            # Request historical data
            self.app.reqHistoricalData(
                req_id, contract, end_time_str, duration, bar_size,
                "MIDPOINT", 1, 1, False, []
            )
            
            # Wait for completion (timeout after 30 seconds)
            timeout = 30
            while timeout > 0 and not self.app.historical_data_complete.get(req_id, False):
                time.sleep(0.5)
                timeout -= 0.5
                
            if timeout <= 0:
                self.logger.error("Historical data request timed out")
                return None
                
            # Convert to DataFrame
            if req_id in self.app.historical_data and self.app.historical_data[req_id]:
                df = pd.DataFrame(self.app.historical_data[req_id])
                df.set_index('datetime', inplace=True)
                df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
                
                self.logger.info(f"✅ Retrieved {len(df)} historical bars for {symbol}")
                return df
            else:
                self.logger.warning("No historical data received")
                return None
                
        except Exception as e:
            self.logger.error(f"Historical data error: {e}")
            return None
        
    def connect(self) -> bool:
        """Synchronous connect method for compatibility"""
        try:
            self.logger.info(f"Connecting to IB TWS at {self.host}:{self.port}")
            
            # Start connection in separate thread
            self.app.connect(self.host, self.port, self.client_id)
            
            # Start message processing thread
            self.connection_thread = threading.Thread(target=self.app.run, daemon=True)
            self.connection_thread.start()
            
            # Wait for connection
            for _ in range(50):  # 5 second timeout
                if self.app.connected:
                    self.is_connected = True
                    self.logger.info("✅ Connected to IB TWS")
                    # Add small delay for initialization
                    time.sleep(1)
                    return True
                time.sleep(0.1)
                
            self.logger.error("❌ Failed to connect to IB TWS")
            return False
            
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            return False
            
    async def async_connect(self) -> bool:
        """Async version of connect"""
        try:
            self.logger.info(f"Connecting to IB TWS at {self.host}:{self.port}")
            
            # Start connection in separate thread
            self.app.connect(self.host, self.port, self.client_id)
            
            # Start message processing thread
            self.connection_thread = threading.Thread(target=self.app.run, daemon=True)
            self.connection_thread.start()
            
            # Wait for connection
            for _ in range(50):  # 5 second timeout
                if self.app.connected:
                    self.is_connected = True
                    self.logger.info("✅ Connected to IB TWS")
                    # Add small delay for initialization
                    await asyncio.sleep(1)
                    return True
                await asyncio.sleep(0.1)
                
            self.logger.error("❌ Failed to connect to IB TWS")
            return False
            
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            return False


class IBPaperTradingEngine:
    """
    Paper trading engine using Interactive Brokers data
    """
    
    def __init__(self, account_type: str = "paper"):
        self.account_type = account_type
        
        # IB connection (paper trading typically uses port 7497)
        port = 7497 if account_type == "paper" else 7496
        self.ib_provider = IBDataProvider(port=port)
        
        # Atlas strategy integration
        self.initial_balance = 50000.0
        self.current_equity = 50000.0
        self.positions = {}
        self.trades = []
        
        self.logger = logging.getLogger(__name__)
        
    async def start_paper_trading(self, symbols: List[str] = None):
        """Start paper trading with IB data"""
        if symbols is None:
            symbols = ["NQ"]  # Default to NQ for Atlas strategy
            
        self.logger.info("🚀 Starting IB Paper Trading")
        
        # Connect to IB
        if not await self.ib_provider.async_connect():
            self.logger.error("Failed to connect to IB TWS")
            return
            
        # Subscribe to market data
        for symbol in symbols:
            if symbol == "NQ":
                success = await self.ib_provider.subscribe_to_market_data(symbol, "FUT")
            else:
                success = await self.ib_provider.subscribe_to_market_data(symbol, "STK")
                
            if success:
                self.logger.info(f"✅ Subscribed to {symbol}")
            else:
                self.logger.error(f"❌ Failed to subscribe to {symbol}")
                
        # Subscribe to data updates
        self.ib_provider.subscribe(self._on_market_data)
        
        try:
            # Keep running until interrupted
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("Paper trading stopped by user")
        finally:
            self.ib_provider.disconnect()
            
    async def _on_market_data(self, market_data: Dict):
        """Handle incoming market data"""
        symbol = market_data['symbol']
        price = market_data['price']
        timestamp = market_data['timestamp']
        
        self.logger.info(f"📊 {symbol}: ${price:.2f} at {timestamp.strftime('%H:%M:%S')}")
        
        # Here you would integrate with your Atlas strategy logic
        # For now, just log the data


# Setup and testing functions
async def test_ib_connection():
    """Test IB connection and data feed"""
    print("🔍 Testing Interactive Brokers Connection")
    print("=" * 40)
    
    if not IB_AVAILABLE:
        print("❌ IB API not installed")
        print("Install with: pip install ibapi")
        return False
        
    # Create test engine
    engine = IBPaperTradingEngine("paper")
    
    try:
        # Test connection
        if await engine.ib_provider.async_connect():
            print("✅ Connected to IB TWS")
            
            # Test market data subscription
            print("Testing market data subscription...")
            
            # Subscribe to data
            data_received = []
            
            def collect_data(data):
                data_received.append(data)
                print(f"📊 {data['symbol']}: ${data['price']:.2f}")
                
            engine.ib_provider.subscribe(collect_data)
            
            # For UK equities (your available data)
            await engine.ib_provider.subscribe_to_market_data("BARC", "STK")  # Barclays example
            
            # Wait for data
            print("Collecting data for 30 seconds...")
            await asyncio.sleep(30)
            
            print(f"✅ Received {len(data_received)} data points")
            
            return len(data_received) > 0
            
        else:
            print("❌ Failed to connect to IB TWS")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        engine.ib_provider.disconnect()


if __name__ == "__main__":
    print("🎯 Interactive Brokers Integration for Atlas Strategy")
    print()
    
    if not IB_AVAILABLE:
        print("📦 Installation required:")
        print("pip install ibapi")
        print()
    else:
        print("🧪 Running connection test...")
        asyncio.run(test_ib_connection())
