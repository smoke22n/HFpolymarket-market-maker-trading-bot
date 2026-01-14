"""
Database layer for the Polymarket MM Bot
Handles persistence of trades, PnL snapshots, active orders, and bot configuration
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Numeric, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from decimal import Decimal
import os

Base = declarative_base()

class Trade(Base):
    """
    Table to store executed fills
    Fields: timestamp, market_id, side, price, size, fee, tx_hash
    """
    __tablename__ = 'trades'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    market_id = Column(String(255), nullable=False)
    side = Column(String(10), nullable=False)  # 'buy' or 'sell'
    price = Column(Numeric(precision=20, scale=10), nullable=False)
    size = Column(Numeric(precision=20, scale=10), nullable=False)
    fee = Column(Numeric(precision=20, scale=10))
    tx_hash = Column(String(255))

    def __repr__(self):
        return f"<Trade(timestamp={self.timestamp}, market_id={self.market_id}, side={self.side}, price={self.price}, size={self.size})>"


class PnLSnapshot(Base):
    """
    Table to record equity every minute
    Fields: timestamp, total_usdc, total_positions_value, cumulative_pnl
    """
    __tablename__ = 'pnl_snapshots'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    total_usdc = Column(Numeric(precision=20, scale=10), nullable=False)
    total_positions_value = Column(Numeric(precision=20, scale=10), nullable=False)
    cumulative_pnl = Column(Numeric(precision=20, scale=10), nullable=False)

    def __repr__(self):
        return f"<PnLSnapshot(timestamp={self.timestamp}, total_usdc={self.total_usdc}, total_positions_value={self.total_positions_value}, cumulative_pnl={self.cumulative_pnl})>"


class ActiveOrder(Base):
    """
    Table that syncs with the live memory of the bot
    Fields: order_id, market_id, side, price, size, status, created_at, updated_at
    """
    __tablename__ = 'active_orders'

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(255), unique=True, nullable=False)
    market_id = Column(String(255), nullable=False)
    side = Column(String(10), nullable=False)  # 'buy' or 'sell'
    price = Column(Numeric(precision=20, scale=10), nullable=False)
    size = Column(Numeric(precision=20, scale=10), nullable=False)
    status = Column(String(20), default='open', nullable=False)  # 'open', 'filled', 'cancelled', 'partially_filled'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<ActiveOrder(order_id={self.order_id}, market_id={self.market_id}, side={self.side}, price={self.price}, size={self.size}, status={self.status})>"


class BotConfig(Base):
    """
    Table to store parameters (spread, max_exposure) so they can be changed without restarting
    Fields: param_name, param_value, description, updated_at
    """
    __tablename__ = 'bot_configs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    param_name = Column(String(255), unique=True, nullable=False)
    param_value = Column(String(255), nullable=False)
    description = Column(String(500))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<BotConfig(param_name={self.param_name}, param_value={self.param_value})>"


class DatabaseManager:
    """
    Manages database connections and operations
    """
    def __init__(self, db_path: str = "polymarket_bot.db"):
        # Use SQLite database file
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Create tables
        Base.metadata.create_all(bind=self.engine)

    def get_db(self):
        """
        Dependency to get database session
        """
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def save_trade(self, market_id: str, side: str, price: Decimal, size: Decimal, fee: Decimal = None, tx_hash: str = None):
        """
        Save a trade to the database
        """
        db = self.SessionLocal()
        try:
            trade = Trade(
                market_id=market_id,
                side=side,
                price=float(price),
                size=float(size),
                fee=float(fee) if fee else None,
                tx_hash=tx_hash
            )
            db.add(trade)
            db.commit()
            db.refresh(trade)
            return trade
        finally:
            db.close()

    def save_pnl_snapshot(self, total_usdc: Decimal, total_positions_value: Decimal, cumulative_pnl: Decimal):
        """
        Save a PnL snapshot to the database
        """
        db = self.SessionLocal()
        try:
            snapshot = PnLSnapshot(
                total_usdc=float(total_usdc),
                total_positions_value=float(total_positions_value),
                cumulative_pnl=float(cumulative_pnl)
            )
            db.add(snapshot)
            db.commit()
            db.refresh(snapshot)
            return snapshot
        finally:
            db.close()

    def save_active_order(self, order_id: str, market_id: str, side: str, price: Decimal, size: Decimal, status: str = 'open'):
        """
        Save or update an active order in the database
        """
        db = self.SessionLocal()
        try:
            # Check if order already exists
            order = db.query(ActiveOrder).filter(ActiveOrder.order_id == order_id).first()
            
            if order:
                # Update existing order
                order.market_id = market_id
                order.side = side
                order.price = float(price)
                order.size = float(size)
                order.status = status
                order.updated_at = datetime.utcnow()
            else:
                # Create new order
                order = ActiveOrder(
                    order_id=order_id,
                    market_id=market_id,
                    side=side,
                    price=float(price),
                    size=float(size),
                    status=status
                )
                db.add(order)
            
            db.commit()
            if not order.id:
                db.refresh(order)
            return order
        finally:
            db.close()

    def update_order_status(self, order_id: str, status: str):
        """
        Update the status of an active order
        """
        db = self.SessionLocal()
        try:
            order = db.query(ActiveOrder).filter(ActiveOrder.order_id == order_id).first()
            if order:
                order.status = status
                order.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(order)
                return order
        finally:
            db.close()

    def remove_active_order(self, order_id: str):
        """
        Remove an active order from the database (when filled/cancelled)
        """
        db = self.SessionLocal()
        try:
            order = db.query(ActiveOrder).filter(ActiveOrder.order_id == order_id).first()
            if order:
                db.delete(order)
                db.commit()
                return True
            return False
        finally:
            db.close()

    def get_active_orders(self, market_id: str = None):
        """
        Get all active orders, optionally filtered by market_id
        """
        db = self.SessionLocal()
        try:
            query = db.query(ActiveOrder)
            if market_id:
                query = query.filter(ActiveOrder.market_id == market_id)
            return query.all()
        finally:
            db.close()

    def save_bot_config(self, param_name: str, param_value: str, description: str = None):
        """
        Save or update a bot configuration parameter
        """
        db = self.SessionLocal()
        try:
            # Check if config already exists
            config = db.query(BotConfig).filter(BotConfig.param_name == param_name).first()
            
            if config:
                # Update existing config
                config.param_value = param_value
                config.description = description
                config.updated_at = datetime.utcnow()
            else:
                # Create new config
                config = BotConfig(
                    param_name=param_name,
                    param_value=param_value,
                    description=description
                )
                db.add(config)
            
            db.commit()
            if not config.id:
                db.refresh(config)
            return config
        finally:
            db.close()

    def get_bot_config(self, param_name: str):
        """
        Get a bot configuration parameter
        """
        db = self.SessionLocal()
        try:
            config = db.query(BotConfig).filter(BotConfig.param_name == param_name).first()
            return config
        finally:
            db.close()

    def get_all_bot_configs(self):
        """
        Get all bot configuration parameters
        """
        db = self.SessionLocal()
        try:
            return db.query(BotConfig).all()
        finally:
            db.close()


# Global database manager instance
db_manager = DatabaseManager()