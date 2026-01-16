"""
Configuration for Polymarket Market Maker Bot
"""
import os
from dataclasses import dataclass
from typing import Optional
from decimal import Decimal
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class PolymarketConfig:
    """Configuration for Polymarket API"""
    api_key: str
    secret_key: str
    wallet_address: str
    base_url: str = "https://clob.polymarket.com"
    ws_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    rate_limit_max_requests: int = 500
    rate_limit_time_window: int = 10
    heartbeat_interval: int = 30
    reconnect_delay: int = 5
    max_reconnect_attempts: int = 10
    dry_run: bool = False
    dry_run_log_file: str = "dry_run_log.json"
    starting_balance: Decimal = Decimal('10000')


def load_config() -> PolymarketConfig:
    """Load configuration from environment variables"""
    from decimal import Decimal
    return PolymarketConfig(
        api_key=os.getenv("POLYMARKET_API_KEY", ""),
        secret_key=os.getenv("POLYMARKET_SECRET_KEY", ""),
        wallet_address=os.getenv("POLYMARKET_WALLET_ADDRESS", ""),
        base_url=os.getenv("POLYMARKET_BASE_URL", "https://clob.polymarket.com"),
        ws_url=os.getenv("POLYMARKET_WS_URL", "wss://clob.polymarket.com/ws"),
        rate_limit_max_requests=int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "500")),
        rate_limit_time_window=int(os.getenv("RATE_LIMIT_TIME_WINDOW", "10")),
        heartbeat_interval=int(os.getenv("HEARTBEAT_INTERVAL", "30")),
        reconnect_delay=int(os.getenv("RECONNECT_DELAY", "5")),
        max_reconnect_attempts=int(os.getenv("MAX_RECONNECT_ATTEMPTS", "10")),
        dry_run=os.getenv("DRY_RUN", "false").lower() == "true",
        dry_run_log_file=os.getenv("DRY_RUN_LOG_FILE", "dry_run_log.json"),
        starting_balance=Decimal(os.getenv("STARTING_BALANCE", "10000"))
    )