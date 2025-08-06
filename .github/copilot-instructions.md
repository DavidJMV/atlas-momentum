<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# FTMO Algorithmic Trading Strategy Project

This project implements a quantitative trading strategy designed specifically for passing FTMO evaluations with high probability.

## Key Context for Copilot:

- **Primary Focus**: NQ (NASDAQ-100) CFD trading on 1-minute timeframes
- **Risk Management**: Strict adherence to FTMO rules (5% daily loss, 10% total loss limits)
- **Technology Stack**: Python 3.13, Backtrader, cTrader Open API, pandas, numpy, ta-lib
- **Target**: ≥70% pass rate on FTMO £50k "Normal" account evaluations
- **Trading Style**: Momentum-based with adaptive mean-reversion capabilities

## Code Style Preferences:
- Use type hints for all function parameters and return values
- Implement comprehensive error handling with specific exception types
- Follow PEP 8 standards with 88-character line limits
- Include detailed docstrings with parameter descriptions and examples
- Prefer composition over inheritance for strategy components
- Use dataclasses for configuration objects
- Implement proper logging throughout all modules

## Architecture Guidelines:
- Separate concerns: strategy logic, risk management, data handling, execution
- Use dependency injection for testability
- Implement proper state management for live trading
- Create modular components that can be easily backtested and optimized
- Design for both backtesting and live execution without code changes
