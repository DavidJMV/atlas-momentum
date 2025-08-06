"""
Real Data Integration for Atlas Strategy
Connects to various market data providers for live trading
"""

import aiohttp
import asyncio
import json
import websockets
from typing import Dict, List, Optional, Callable
from datetime import datetime
import logging
from dataclasses import dataclass

from config.config import config


@dataclass
class MarketData:
    """Market data structure"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    bid: Optional[float] = None
    ask: Optional[float] = None


class AlphaVantageProvider:
    """
    Alpha Vantage data provider
    Free tier: 5 API requests per minute, 500 per day
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
        
    async def get_realtime_quote(self, symbol: str) -> Optional[MarketData]:
        """Get real-time quote data"""
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': symbol,
            'apikey': self.api_key
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self.base_url, params=params) as response:
                    data = await response.json()
                    
                    if 'Global Quote' in data:
                        quote = data['Global Quote']
                        return MarketData(
                            symbol=symbol,
                            timestamp=datetime.now(),
                            open=float(quote['02. open']),
                            high=float(quote['03. high']),
                            low=float(quote['04. low']),
                            close=float(quote['05. price']),
                            volume=int(quote['06. volume'])
                        )
                        
            except Exception as e:
                logging.error(f"Alpha Vantage error: {e}")
                
        return None


class TwelveDataProvider:
    """
    Twelve Data provider
    Free tier: 800 requests per day
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.twelvedata.com"
        
    async def get_realtime_quote(self, symbol: str) -> Optional[MarketData]:
        """Get real-time quote"""
        url = f"{self.base_url}/price"
        params = {
            'symbol': symbol,
            'apikey': self.api_key
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params) as response:
                    data = await response.json()
                    
                    if 'price' in data:
                        price = float(data['price'])
                        return MarketData(
                            symbol=symbol,
                            timestamp=datetime.now(),
                            open=price,
                            high=price,
                            low=price,
                            close=price,
                            volume=0,
                            bid=price - 0.25,
                            ask=price + 0.25
                        )
                        
            except Exception as e:
                logging.error(f"Twelve Data error: {e}")
                
        return None
        
    async def get_intraday_data(self, symbol: str, interval: str = "1min") -> List[MarketData]:
        """Get intraday data"""
        url = f"{self.base_url}/time_series"
        params = {
            'symbol': symbol,
            'interval': interval,
            'apikey': self.api_key,
            'outputsize': 100  # Last 100 bars
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params) as response:
                    data = await response.json()
                    
                    if 'values' in data:
                        bars = []
                        for bar in data['values']:
                            bars.append(MarketData(
                                symbol=symbol,
                                timestamp=datetime.fromisoformat(bar['datetime']),
                                open=float(bar['open']),
                                high=float(bar['high']),
                                low=float(bar['low']),
                                close=float(bar['close']),
                                volume=int(bar['volume'])
                            ))
                        return bars
                        
            except Exception as e:
                logging.error(f"Twelve Data intraday error: {e}")
                
        return []


class YahooFinanceProvider:
    """
    Yahoo Finance provider (free but rate limited)
    """
    
    def __init__(self):
        self.base_url = "https://query1.finance.yahoo.com/v8/finance/chart"
        
    async def get_realtime_quote(self, symbol: str) -> Optional[MarketData]:
        """Get real-time quote from Yahoo Finance"""
        url = f"{self.base_url}/{symbol}"
        params = {
            'interval': '1m',
            'range': '1d'
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params) as response:
                    data = await response.json()
                    
                    if 'chart' in data and data['chart']['result']:
                        result = data['chart']['result'][0]
                        meta = result['meta']
                        
                        return MarketData(
                            symbol=symbol,
                            timestamp=datetime.now(),
                            open=meta.get('regularMarketPrice', 0),
                            high=meta.get('regularMarketDayHigh', 0),
                            low=meta.get('regularMarketDayLow', 0),
                            close=meta.get('regularMarketPrice', 0),
                            volume=meta.get('regularMarketVolume', 0),
                            bid=meta.get('bid', 0),
                            ask=meta.get('ask', 0)
                        )
                        
            except Exception as e:
                logging.error(f"Yahoo Finance error: {e}")
                
        return None


class DataFeedManager:
    """
    Manages multiple data providers with fallback
    """
    
    def __init__(self):
        self.providers = []
        self.current_provider_index = 0
        self.subscribers = []
        self.is_running = False
        self.logger = logging.getLogger(__name__)
        
        # Initialize available providers
        self._setup_providers()
        
    def _setup_providers(self):
        """Setup available data providers"""
        
        # Add Alpha Vantage if API key available
        alpha_vantage_key = self._get_env_var("ALPHA_VANTAGE_API_KEY")
        if alpha_vantage_key:
            self.providers.append(AlphaVantageProvider(alpha_vantage_key))
            self.logger.info("Alpha Vantage provider added")
            
        # Add Twelve Data if API key available
        twelve_data_key = self._get_env_var("TWELVE_DATA_API_KEY")
        if twelve_data_key:
            self.providers.append(TwelveDataProvider(twelve_data_key))
            self.logger.info("Twelve Data provider added")
            
        # Add Yahoo Finance (free, no API key needed)
        self.providers.append(YahooFinanceProvider())
        self.logger.info("Yahoo Finance provider added")
        
        if not self.providers:
            self.logger.warning("No data providers configured")
            
    def _get_env_var(self, var_name: str) -> Optional[str]:
        """Get environment variable"""
        import os
        return os.getenv(var_name)
        
    def subscribe(self, callback: Callable):
        """Subscribe to market data updates"""
        self.subscribers.append(callback)
        
    async def start_feed(self, symbol: str = "NQ=F", update_interval: int = 5):
        """
        Start real-time data feed
        
        Args:
            symbol: Trading symbol (NQ=F for NASDAQ-100 futures)
            update_interval: Update interval in seconds
        """
        self.is_running = True
        self.logger.info(f"Starting data feed for {symbol}")
        
        while self.is_running:
            try:
                # Get data from current provider
                data = await self._get_market_data(symbol)
                
                if data:
                    # Notify subscribers
                    for callback in self.subscribers:
                        try:
                            await callback(data)
                        except Exception as e:
                            self.logger.error(f"Subscriber callback error: {e}")
                else:
                    # Try next provider if current one fails
                    self._switch_provider()
                    
                await asyncio.sleep(update_interval)
                
            except Exception as e:
                self.logger.error(f"Data feed error: {e}")
                await asyncio.sleep(1)
                
    async def _get_market_data(self, symbol: str) -> Optional[MarketData]:
        """Get market data from current provider"""
        if not self.providers:
            return None
            
        provider = self.providers[self.current_provider_index]
        
        try:
            return await provider.get_realtime_quote(symbol)
        except Exception as e:
            self.logger.error(f"Provider {type(provider).__name__} error: {e}")
            return None
            
    def _switch_provider(self):
        """Switch to next available provider"""
        if len(self.providers) > 1:
            self.current_provider_index = (self.current_provider_index + 1) % len(self.providers)
            current_provider = self.providers[self.current_provider_index]
            self.logger.info(f"Switched to provider: {type(current_provider).__name__}")
            
    def stop_feed(self):
        """Stop data feed"""
        self.is_running = False
        self.logger.info("Data feed stopped")
        
    async def get_historical_data(self, symbol: str, interval: str = "1min") -> List[MarketData]:
        """Get historical intraday data"""
        for provider in self.providers:
            if hasattr(provider, 'get_intraday_data'):
                try:
                    data = await provider.get_intraday_data(symbol, interval)
                    if data:
                        return data
                except Exception as e:
                    self.logger.error(f"Historical data error: {e}")
                    continue
                    
        return []


# Example usage and testing
async def test_data_feed():
    """Test the data feed functionality"""
    
    print("🔍 Testing Real Market Data Feed")
    print("=" * 40)
    
    # Create data feed manager
    feed_manager = DataFeedManager()
    
    # Subscribe to data updates
    async def on_data_update(market_data: MarketData):
        print(f"{market_data.timestamp.strftime('%H:%M:%S')} | "
              f"{market_data.symbol} | "
              f"Price: {market_data.close:.2f} | "
              f"Vol: {market_data.volume:,}")
              
    feed_manager.subscribe(on_data_update)
    
    try:
        # Test with NASDAQ-100 futures symbol
        # Note: Symbol format may vary by provider
        symbols_to_try = ["NQ=F", "NDX", "^NDX", "NAS100"]
        
        for symbol in symbols_to_try:
            print(f"\nTrying symbol: {symbol}")
            
            # Start feed for 30 seconds
            feed_task = asyncio.create_task(feed_manager.start_feed(symbol, update_interval=2))
            
            # Let it run for 30 seconds
            await asyncio.sleep(30)
            
            # Stop feed
            feed_manager.stop_feed()
            break
            
    except KeyboardInterrupt:
        print("\nData feed test interrupted")
        feed_manager.stop_feed()


if __name__ == "__main__":
    # Test the data feed
    asyncio.run(test_data_feed())
