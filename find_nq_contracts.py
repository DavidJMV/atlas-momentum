#!/usr/bin/env python3
"""
Contract Search Test
Find available NQ contracts
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import threading
import time

class ContractApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.contracts = []
        
    def contractDetails(self, reqId, contractDetails):
        contract = contractDetails.contract
        print(f"📋 Found: {contract.symbol} {contract.lastTradeDateOrContractMonth} - {contractDetails.longName}")
        self.contracts.append(contract)
        
    def contractDetailsEnd(self, reqId):
        print(f"✅ Found {len(self.contracts)} contracts")

def find_nq_contracts():
    """Find available NQ contracts"""
    print("🔍 SEARCHING FOR NQ CONTRACTS")
    print("=" * 40)
    
    app = ContractApp()
    
    try:
        # Connect
        print("🔌 Connecting...")
        app.connect("127.0.0.1", 7497, 0)
        
        # Start message loop in thread
        thread = threading.Thread(target=app.run, daemon=True)
        thread.start()
        
        # Wait for connection
        time.sleep(2)
        
        # Create generic NQ contract
        contract = Contract()
        contract.symbol = "NQ"
        contract.secType = "FUT"
        contract.exchange = "CME"
        contract.currency = "USD"
        
        print("🔍 Searching for NQ contracts...")
        app.reqContractDetails(1, contract)
        
        # Wait for results
        time.sleep(10)
        
        return app.contracts
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return []
        
    finally:
        app.disconnect()

if __name__ == "__main__":
    contracts = find_nq_contracts()
    
    if contracts:
        print("\n📊 Active NQ Contracts:")
        for contract in contracts[:5]:  # Show first 5
            print(f"   {contract.lastTradeDateOrContractMonth}")
    else:
        print("❌ No contracts found")
