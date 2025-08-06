"""
cTrader Open API Integration
Live execution engine for FTMO trading
"""

import asyncio
import json
import ssl
import websocket
import threading
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
from enum import Enum

from config.config import config


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Order:
    """Order data structure"""
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    order_id: Optional[str] = None
    client_order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    average_price: Optional[float] = None
    timestamp: Optional[datetime] = None
    

@dataclass
class Position:
    """Position data structure"""
    symbol: str
    side: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float = 0.0


@dataclass
class AccountInfo:
    """Account information structure"""
    balance: float
    equity: float
    free_margin: float
    margin_level: float
    unrealized_pnl: float


class CTraderAPIClient:
    """
    cTrader Open API Client for live trading
    Handles authentication, order management, and real-time data
    """
    
    def __init__(self, api_url: str = None, api_key: str = None, secret: str = None):
        self.api_url = api_url or config.broker.api_url
        self.api_key = api_key
        self.secret = secret
        
        # Connection management
        self.ws = None
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = config.broker.reconnect_attempts
        
        # Data storage
        self.account_info: Optional[AccountInfo] = None
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.price_data: Dict[str, Dict] = {}
        
        # Callbacks
        self.on_price_update: Optional[Callable] = None
        self.on_order_update: Optional[Callable] = None
        self.on_position_update: Optional[Callable] = None
        self.on_account_update: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
    def connect(self) -> bool:
        """
        Connect to cTrader API
        
        Returns:
            bool: True if connection successful
        """
        try:
            # Create WebSocket connection
            self.ws = websocket.WebSocketApp(
                self.api_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            # Start connection in separate thread
            self.ws_thread = threading.Thread(target=self.ws.run_forever, kwargs={"sslopt": {"cert_reqs": ssl.CERT_NONE}})
            self.ws_thread.daemon = True
            self.ws_thread.start()
            
            # Wait for connection
            timeout = 10
            while not self.is_connected and timeout > 0:
                time.sleep(0.1)
                timeout -= 0.1
                
            return self.is_connected
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            if self.on_error:
                self.on_error(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from cTrader API"""
        if self.ws:
            self.is_connected = False
            self.ws.close()
            
    def _on_open(self, ws):
        """WebSocket connection opened"""
        self.logger.info("Connected to cTrader API")
        self.is_connected = True
        self.reconnect_attempts = 0
        
        # Send authentication
        self._authenticate()
        
        # Subscribe to account updates
        self._subscribe_to_account()
        
    def _on_message(self, ws, message):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == 'PRICE_UPDATE':
                self._handle_price_update(data)
            elif msg_type == 'ORDER_UPDATE':
                self._handle_order_update(data)
            elif msg_type == 'POSITION_UPDATE':
                self._handle_position_update(data)
            elif msg_type == 'ACCOUNT_UPDATE':
                self._handle_account_update(data)
            elif msg_type == 'ERROR':
                self._handle_error_message(data)
                
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            
    def _on_error(self, ws, error):
        """WebSocket error handler"""
        self.logger.error(f"WebSocket error: {error}")
        if self.on_error:
            self.on_error(f"WebSocket error: {error}")
            
    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket connection closed"""
        self.logger.info("Connection closed")
        self.is_connected = False
        
        # Attempt reconnection if not intentional
        if self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            self.logger.info(f"Attempting reconnection {self.reconnect_attempts}/{self.max_reconnect_attempts}")
            time.sleep(5)
            self.connect()
            
    def _authenticate(self):
        """Send authentication message"""
        auth_message = {
            'type': 'AUTH',
            'api_key': self.api_key,
            'timestamp': int(time.time() * 1000)
        }
        # Add signature logic here based on cTrader API requirements
        self._send_message(auth_message)
        
    def _subscribe_to_account(self):
        """Subscribe to account and position updates"""
        subscribe_message = {
            'type': 'SUBSCRIBE',
            'channels': ['account', 'positions', 'orders']
        }
        self._send_message(subscribe_message)
        
    def subscribe_to_symbol(self, symbol: str):
        """Subscribe to price updates for a symbol"""
        subscribe_message = {
            'type': 'SUBSCRIBE_SYMBOL',
            'symbol': symbol
        }
        self._send_message(subscribe_message)
        
    def _send_message(self, message: dict):
        """Send message via WebSocket"""
        if self.ws and self.is_connected:
            self.ws.send(json.dumps(message))
            
    def place_market_order(
        self, 
        symbol: str, 
        side: OrderSide, 
        quantity: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Optional[str]:
        """
        Place market order
        
        Args:
            symbol: Trading symbol
            side: Order side (BUY/SELL)
            quantity: Order quantity
            stop_loss: Stop loss price
            take_profit: Take profit price
            
        Returns:
            str: Client order ID if successful
        """
        
        client_order_id = f"market_{symbol}_{int(time.time() * 1000)}"
        
        order_message = {
            'type': 'PLACE_ORDER',
            'clientOrderId': client_order_id,
            'symbol': symbol,
            'side': side.value,
            'orderType': OrderType.MARKET.value,
            'quantity': quantity
        }
        
        if stop_loss:
            order_message['stopLoss'] = stop_loss
            
        if take_profit:
            order_message['takeProfit'] = take_profit
            
        # Store order locally
        order = Order(
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            client_order_id=client_order_id,
            timestamp=datetime.now()
        )
        self.orders[client_order_id] = order
        
        self._send_message(order_message)
        return client_order_id
        
    def place_limit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Optional[str]:
        """Place limit order"""
        
        client_order_id = f"limit_{symbol}_{int(time.time() * 1000)}"
        
        order_message = {
            'type': 'PLACE_ORDER',
            'clientOrderId': client_order_id,
            'symbol': symbol,
            'side': side.value,
            'orderType': OrderType.LIMIT.value,
            'quantity': quantity,
            'price': price
        }
        
        if stop_loss:
            order_message['stopLoss'] = stop_loss
            
        if take_profit:
            order_message['takeProfit'] = take_profit
            
        # Store order locally
        order = Order(
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=price,
            client_order_id=client_order_id,
            timestamp=datetime.now()
        )
        self.orders[client_order_id] = order
        
        self._send_message(order_message)
        return client_order_id
        
    def cancel_order(self, client_order_id: str) -> bool:
        """Cancel an order"""
        cancel_message = {
            'type': 'CANCEL_ORDER',
            'clientOrderId': client_order_id
        }
        
        self._send_message(cancel_message)
        return True
        
    def close_position(self, symbol: str, quantity: Optional[float] = None) -> bool:
        """Close position (full or partial)"""
        position = self.positions.get(symbol)
        if not position:
            return False
            
        close_quantity = quantity or abs(position.quantity)
        close_side = OrderSide.SELL if position.quantity > 0 else OrderSide.BUY
        
        return self.place_market_order(symbol, close_side, close_quantity) is not None
        
    def modify_position_stops(
        self,
        symbol: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> bool:
        """Modify stop loss and take profit for existing position"""
        
        modify_message = {
            'type': 'MODIFY_POSITION',
            'symbol': symbol
        }
        
        if stop_loss is not None:
            modify_message['stopLoss'] = stop_loss
            
        if take_profit is not None:
            modify_message['takeProfit'] = take_profit
            
        self._send_message(modify_message)
        return True
        
    def get_current_price(self, symbol: str) -> Optional[Dict]:
        """Get current bid/ask prices for symbol"""
        return self.price_data.get(symbol)
        
    def get_account_info(self) -> Optional[AccountInfo]:
        """Get current account information"""
        return self.account_info
        
    def get_positions(self) -> Dict[str, Position]:
        """Get all current positions"""
        return self.positions.copy()
        
    def get_orders(self) -> Dict[str, Order]:
        """Get all orders"""
        return self.orders.copy()
        
    def _handle_price_update(self, data: dict):
        """Handle price update message"""
        symbol = data.get('symbol')
        if symbol:
            self.price_data[symbol] = {
                'bid': data.get('bid'),
                'ask': data.get('ask'),
                'timestamp': datetime.now()
            }
            
            if self.on_price_update:
                self.on_price_update(symbol, self.price_data[symbol])
                
    def _handle_order_update(self, data: dict):
        """Handle order update message"""
        client_order_id = data.get('clientOrderId')
        if client_order_id and client_order_id in self.orders:
            order = self.orders[client_order_id]
            order.status = OrderStatus(data.get('status', 'PENDING'))
            order.filled_quantity = data.get('filledQuantity', 0.0)
            order.average_price = data.get('averagePrice')
            
            if self.on_order_update:
                self.on_order_update(order)
                
    def _handle_position_update(self, data: dict):
        """Handle position update message"""
        symbol = data.get('symbol')
        if symbol:
            position = Position(
                symbol=symbol,
                side=data.get('side'),
                quantity=data.get('quantity', 0.0),
                entry_price=data.get('entryPrice', 0.0),
                current_price=data.get('currentPrice', 0.0),
                unrealized_pnl=data.get('unrealizedPnl', 0.0),
                realized_pnl=data.get('realizedPnl', 0.0)
            )
            
            if position.quantity == 0:
                # Position closed
                if symbol in self.positions:
                    del self.positions[symbol]
            else:
                self.positions[symbol] = position
                
            if self.on_position_update:
                self.on_position_update(position)
                
    def _handle_account_update(self, data: dict):
        """Handle account update message"""
        self.account_info = AccountInfo(
            balance=data.get('balance', 0.0),
            equity=data.get('equity', 0.0),
            free_margin=data.get('freeMargin', 0.0),
            margin_level=data.get('marginLevel', 0.0),
            unrealized_pnl=data.get('unrealizedPnl', 0.0)
        )
        
        if self.on_account_update:
            self.on_account_update(self.account_info)
            
    def _handle_error_message(self, data: dict):
        """Handle error message from API"""
        error_msg = data.get('message', 'Unknown error')
        self.logger.error(f"API Error: {error_msg}")
        
        if self.on_error:
            self.on_error(error_msg)


class TradingEngine:
    """
    High-level trading engine that integrates strategy with execution
    """
    
    def __init__(self, api_client: CTraderAPIClient):
        self.api_client = api_client
        self.is_trading = False
        self.current_orders: Dict[str, str] = {}  # strategy_order_id -> api_order_id
        self.logger = logging.getLogger(__name__)
        
        # Set up callbacks
        self.api_client.on_order_update = self._on_order_update
        self.api_client.on_position_update = self._on_position_update
        self.api_client.on_error = self._on_error
        
    def start_trading(self):
        """Start the trading engine"""
        if not self.api_client.is_connected:
            if not self.api_client.connect():
                raise ConnectionError("Failed to connect to broker API")
                
        self.is_trading = True
        self.logger.info("Trading engine started")
        
    def stop_trading(self):
        """Stop the trading engine"""
        self.is_trading = False
        
        # Cancel all pending orders
        self._cancel_all_orders()
        
        # Close all positions if required
        self._close_all_positions()
        
        self.logger.info("Trading engine stopped")
        
    def execute_signal(self, signal: dict) -> bool:
        """
        Execute a trading signal
        
        Args:
            signal: Trading signal dictionary
            
        Returns:
            bool: True if execution successful
        """
        
        if not self.is_trading:
            return False
            
        try:
            symbol = signal.get('symbol', config.trading.symbol)
            side = OrderSide.BUY if signal['type'] == 'LONG' else OrderSide.SELL
            quantity = signal.get('quantity', 1)
            stop_loss = signal.get('stop_loss')
            take_profit = signal.get('take_profit')
            
            # Place market order
            order_id = self.api_client.place_market_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            
            if order_id:
                self.current_orders[signal.get('id', 'unknown')] = order_id
                self.logger.info(f"Signal executed: {signal['type']} {quantity} {symbol}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to execute signal: {e}")
            
        return False
        
    def _cancel_all_orders(self):
        """Cancel all pending orders"""
        for order_id in self.current_orders.values():
            try:
                self.api_client.cancel_order(order_id)
            except Exception as e:
                self.logger.error(f"Failed to cancel order {order_id}: {e}")
                
    def _close_all_positions(self):
        """Close all open positions"""
        positions = self.api_client.get_positions()
        for symbol in positions:
            try:
                self.api_client.close_position(symbol)
            except Exception as e:
                self.logger.error(f"Failed to close position {symbol}: {e}")
                
    def _on_order_update(self, order: Order):
        """Handle order update from API"""
        self.logger.info(f"Order update: {order.client_order_id} - {order.status}")
        
    def _on_position_update(self, position: Position):
        """Handle position update from API"""
        self.logger.info(f"Position update: {position.symbol} - {position.quantity}")
        
    def _on_error(self, error_msg: str):
        """Handle API errors"""
        self.logger.error(f"API Error: {error_msg}")
        
        # Could implement automatic error recovery here
