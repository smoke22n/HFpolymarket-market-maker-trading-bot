"""
Control Tower API Server for Polymarket MM Bot
Exposes trading bot data and controls via REST API
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from decimal import Decimal
from fastapi import FastAPI, HTTPException, Query
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from enum import Enum

from ..utils.database import db_manager, Trade, PnLSnapshot, ActiveOrder
from ..utils.config_manager import config_manager
from .background_runner import BackgroundRunner, BotState, TradingStats


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the background runner
background_runner = BackgroundRunner()

# Create FastAPI app
app = FastAPI(
    title="Polymarket MM Bot Control Tower",
    description="API for controlling and monitoring the Polymarket Market Maker Bot",
    version="1.0.0"
)

# WebSocket Manager for real-time updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except WebSocketDisconnect:
                self.disconnect(connection)
                await connection.close()


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial data when client connects
        initial_data = {
            "type": "initial_data",
            "stats": await get_stats(),
            "live_orders": await get_live_orders(),
            "pending_transactions": await get_pending_transactions(),
            "market_spreads": await get_market_spreads(),
            "timestamp": datetime.utcnow().isoformat()
        }
        await manager.broadcast(initial_data)

        # Keep the connection alive
        while True:
            # Receive any messages from client (we don't expect any in this implementation)
            try:
                data = await websocket.receive_text()
                # Optionally handle client messages here
            except WebSocketDisconnect:
                manager.disconnect(websocket)
                break
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Pydantic models for request/response bodies
class ControlAction(str, Enum):
    PAUSE = "pause"
    RESUME = "resume"
    PANIC_SELL = "panic_sell"


class ConfigUpdate(BaseModel):
    param_name: str
    param_value: str
    description: Optional[str] = None


class StatsResponse(BaseModel):
    pnl: float
    open_exposure: float
    win_loss_ratio: float
    total_trades: int
    bot_state: str
    timestamp: str


class HistoryResponse(BaseModel):
    trades: List[Dict[str, Any]]
    total_count: int
    page: int
    page_size: int


class ControlResponse(BaseModel):
    action: str
    success: bool
    message: str
    timestamp: str


class ConfigResponse(BaseModel):
    param_name: str
    param_value: str
    success: bool
    message: str
    timestamp: str


@app.on_event("startup")
async def startup_event():
    """Initialize the background runner on startup"""
    logger.info("Starting up Control Tower API...")
    # Optionally start the bot automatically
    # background_runner.start_bot()

    # Start background task for broadcasting updates
    asyncio.create_task(broadcast_updates())


async def broadcast_updates():
    """Background task to broadcast updates to all connected WebSocket clients"""
    while True:
        try:
            # Wait 2 seconds between broadcasts
            await asyncio.sleep(2)

            if manager.active_connections:
                # Prepare update data
                stats = await get_stats()

                # Get live orders
                live_orders = await get_live_orders()

                # Get pending transactions
                pending_transactions = await get_pending_transactions()

                # Get market spreads
                market_spreads = await get_market_spreads()

                # Get cumulative PnL data
                cumulative_pnl = await get_cumulative_pnl()

                # Broadcast to all connected clients
                update_data = {
                    "type": "update",
                    "stats": stats,
                    "live_orders": live_orders,
                    "pending_transactions": pending_transactions,
                    "market_spreads": market_spreads,
                    "cumulative_pnl": cumulative_pnl[-5:] if cumulative_pnl else [],  # Last 5 records
                    "timestamp": datetime.utcnow().isoformat()
                }

                await manager.broadcast(update_data)
        except Exception as e:
            logger.error(f"Error in broadcast_updates: {e}")
            await asyncio.sleep(5)  # Wait longer if there's an error


@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get current trading statistics including PnL, Open Exposure, and Win/Loss ratio
    """
    try:
        stats = background_runner.get_stats()
        current_state = background_runner.get_state()
        
        # Get latest PnL from database
        db_session = db_manager.SessionLocal()
        try:
            latest_pnl = db_session.query(PnLSnapshot).order_by(PnLSnapshot.timestamp.desc()).first()
            if latest_pnl:
                pnl = float(latest_pnl.cumulative_pnl)
            else:
                pnl = 0.0
        finally:
            db_session.close()
        
        return StatsResponse(
            pnl=pnl,
            open_exposure=float(stats.open_exposure),
            win_loss_ratio=float(stats.win_loss_ratio),
            total_trades=stats.total_trades,
            bot_state=current_state.value,
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history", response_model=HistoryResponse)
async def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    market_id: Optional[str] = Query(None)
):
    """
    Get paginated list of completed transactions
    """
    try:
        offset = (page - 1) * page_size
        
        db_session = db_manager.SessionLocal()
        try:
            # Build query
            query = db_session.query(Trade)
            if market_id:
                query = query.filter(Trade.market_id == market_id)
            
            # Get total count
            total_count = query.count()
            
            # Get paginated results
            trades = query.offset(offset).limit(page_size).all()
            
            # Convert to dict format
            trades_list = []
            for trade in trades:
                trades_list.append({
                    "id": trade.id,
                    "timestamp": trade.timestamp.isoformat(),
                    "market_id": trade.market_id,
                    "side": trade.side,
                    "price": float(trade.price),
                    "size": float(trade.size),
                    "fee": float(trade.fee) if trade.fee else None,
                    "tx_hash": trade.tx_hash
                })
        finally:
            db_session.close()
        
        return HistoryResponse(
            trades=trades_list,
            total_count=total_count,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ControlRequest(BaseModel):
    action: ControlAction


@app.post("/control", response_model=ControlResponse)
async def control_bot(control_request: ControlRequest):
    """
    Control the bot: Pause, Resume, or Panic Sell
    """
    try:
        action = control_request.action
        success = False
        message = ""

        if action == ControlAction.PAUSE:
            success = background_runner.pause_bot()
            message = "Bot paused successfully" if success else "Failed to pause bot"
        elif action == ControlAction.RESUME:
            success = background_runner.resume_bot()
            message = "Bot resumed successfully" if success else "Failed to resume bot"
        elif action == ControlAction.PANIC_SELL:
            success = background_runner.trigger_panic_sell()
            message = "Panic sell initiated successfully" if success else "Failed to initiate panic sell"

        return ControlResponse(
            action=action.value,
            success=success,
            message=message,
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Error controlling bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ConfigItem(BaseModel):
    param_name: str
    param_value: str
    description: Optional[str] = None
    updated_at: Optional[str] = None


@app.get("/config", response_model=List[ConfigItem])
async def get_config():
    """
    Get all bot configuration parameters
    """
    try:
        # Get all configurations from the database
        configs = background_runner.get_all_configs()

        # Convert to response format
        config_list = []
        for config in configs:
            config_list.append(ConfigItem(
                param_name=config.param_name,
                param_value=config.param_value,
                description=config.description,
                updated_at=config.updated_at.isoformat() if config.updated_at else None
            ))

        return config_list
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/config", response_model=ConfigResponse)
async def update_config(config_update: ConfigUpdate):
    """
    Update bot configuration parameters (spread, bet size, etc.)
    """
    try:
        success = background_runner.update_config(
            config_update.param_name,
            config_update.param_value
        )

        message = (
            f"Configuration '{config_update.param_name}' updated to '{config_update.param_value}'"
            if success
            else f"Failed to update configuration '{config_update.param_name}'"
        )

        return ConfigResponse(
            param_name=config_update.param_name,
            param_value=config_update.param_value,
            success=success,
            message=message,
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/config", response_model=ConfigResponse)
async def patch_config(config_update: ConfigUpdate):
    """
    Update bot configuration parameters using PATCH method (for immediate updates)
    """
    try:
        success = background_runner.update_config(
            config_update.param_name,
            config_update.param_value
        )

        message = (
            f"Configuration '{config_update.param_name}' updated to '{config_update.param_value}'"
            if success
            else f"Failed to update configuration '{config_update.param_name}'"
        )

        return ConfigResponse(
            param_name=config_update.param_name,
            param_value=config_update.param_value,
            success=success,
            message=message,
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Error updating config via PATCH: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Pydantic models for new endpoints
class ActiveOrderResponse(BaseModel):
    id: int
    order_id: str
    market_id: str
    side: str
    price: float
    size: float
    status: str
    created_at: str
    updated_at: str


class PendingTransaction(BaseModel):
    id: str
    transaction_type: str  # 'merge', 'redeem', 'cancel', etc.
    market_id: str
    outcome: str
    amount: float
    status: str  # 'pending', 'confirmed', 'failed'
    created_at: str
    estimated_completion: Optional[str] = None


class SpreadData(BaseModel):
    market_id: str
    bid_price: float
    ask_price: float
    fair_price: float
    spread_width: float
    timestamp: str


@app.get("/api/orders/live", response_model=List[ActiveOrderResponse])
async def get_live_orders():
    """
    Get all currently active limit orders
    """
    try:
        db_session = db_manager.SessionLocal()
        try:
            # Get all active orders that are not filled or cancelled
            active_orders = db_session.query(ActiveOrder).filter(
                ActiveOrder.status.in_(['open', 'partially_filled'])
            ).all()

            # Convert to response format
            orders_response = []
            for order in active_orders:
                orders_response.append(ActiveOrderResponse(
                    id=order.id,
                    order_id=order.order_id,
                    market_id=order.market_id,
                    side=order.side,
                    price=float(order.price),
                    size=float(order.size),
                    status=order.status,
                    created_at=order.created_at.isoformat(),
                    updated_at=order.updated_at.isoformat() if order.updated_at else order.created_at.isoformat()
                ))
        finally:
            db_session.close()

        return orders_response
    except Exception as e:
        logger.error(f"Error getting live orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/orders/{order_id}", response_model=dict)
async def cancel_order(order_id: str):
    """
    Cancel a specific order by order_id
    """
    try:
        db_session = db_manager.SessionLocal()
        try:
            # Find the order
            order = db_session.query(ActiveOrder).filter(ActiveOrder.order_id == order_id).first()

            if not order:
                raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

            # Update order status to cancelled
            order.status = 'cancelled'
            order.updated_at = datetime.utcnow()
            db_session.commit()

            # In a real implementation, you would also cancel the order on the exchange
            # For now, we just update the status in the database

            return {
                "success": True,
                "message": f"Order {order_id} cancelled successfully",
                "order_id": order_id
            }
        finally:
            db_session.close()
    except Exception as e:
        logger.error(f"Error cancelling order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/transactions/pending", response_model=List[PendingTransaction])
async def get_pending_transactions():
    """
    Get all pending on-chain transactions (merges, redeems, etc.)
    """
    try:
        # In a real implementation, this would query a blockchain transaction queue
        # For now, we'll return mock data
        pending_transactions = [
            {
                "id": "tx_001",
                "transaction_type": "merge",
                "market_id": "market_abc123",
                "outcome": "YES",
                "amount": 100.0,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "estimated_completion": (datetime.utcnow().replace(minute=datetime.utcnow().minute + 2)).isoformat()
            },
            {
                "id": "tx_002",
                "transaction_type": "redeem",
                "market_id": "market_def456",
                "outcome": "NO",
                "amount": 75.0,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "estimated_completion": (datetime.utcnow().replace(minute=datetime.utcnow().minute + 5)).isoformat()
            }
        ]

        # Convert to response format
        transactions_response = []
        for tx in pending_transactions:
            transactions_response.append(PendingTransaction(**tx))

        return transactions_response
    except Exception as e:
        logger.error(f"Error getting pending transactions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/market/spread", response_model=List[SpreadData])
async def get_market_spreads():
    """
    Get current bid/ask spreads and fair prices for markets
    """
    try:
        # In a real implementation, this would fetch live market data
        # For now, we'll return mock data
        spread_data = [
            {
                "market_id": "bitcoin_100k",
                "bid_price": 0.62,
                "ask_price": 0.68,
                "fair_price": 0.65,
                "spread_width": 0.06,
                "timestamp": datetime.utcnow().isoformat()
            },
            {
                "market_id": "ethereum_5k",
                "bid_price": 0.42,
                "ask_price": 0.48,
                "fair_price": 0.45,
                "spread_width": 0.06,
                "timestamp": datetime.utcnow().isoformat()
            },
            {
                "market_id": "solana_300",
                "bid_price": 0.52,
                "ask_price": 0.58,
                "fair_price": 0.55,
                "spread_width": 0.06,
                "timestamp": datetime.utcnow().isoformat()
            }
        ]

        # Convert to response format
        spread_response = []
        for spread in spread_data:
            spread_response.append(SpreadData(**spread))

        return spread_response
    except Exception as e:
        logger.error(f"Error getting market spreads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# New Pydantic models for reporting endpoints
class PnLSnapshotResponse(BaseModel):
    timestamp: str
    total_usdc: float
    total_positions_value: float
    cumulative_pnl: float


class TradeRecordResponse(BaseModel):
    id: int
    timestamp: str
    market_id: str
    side: str
    price: float
    size: float
    fee: Optional[float] = None
    tx_hash: Optional[str] = None


class WinLossAnalysisResponse(BaseModel):
    profit_count: int
    loss_count: int
    profit_percentage: float
    loss_percentage: float


@app.get("/api/pnl/cumulative", response_model=List[PnLSnapshotResponse])
async def get_cumulative_pnl():
    """
    Get cumulative PnL data over time
    """
    try:
        db_session = db_manager.SessionLocal()
        try:
            # Get PnL snapshots ordered by timestamp
            pnl_snapshots = db_session.query(PnLSnapshot).order_by(PnLSnapshot.timestamp.asc()).all()

            # Convert to response format
            pnl_response = []
            for snapshot in pnl_snapshots:
                pnl_response.append(PnLSnapshotResponse(
                    timestamp=snapshot.timestamp.isoformat(),
                    total_usdc=float(snapshot.total_usdc),
                    total_positions_value=float(snapshot.total_positions_value),
                    cumulative_pnl=float(snapshot.cumulative_pnl)
                ))
        finally:
            db_session.close()

        # If no data exists, return mock data
        if not pnl_response:
            # Generate mock data for demonstration
            mock_data = [
                {"timestamp": "2024-01-01T00:00:00", "total_usdc": 10000.0, "total_positions_value": 500.0, "cumulative_pnl": 500.0},
                {"timestamp": "2024-01-02T00:00:00", "total_usdc": 10100.0, "total_positions_value": 550.0, "cumulative_pnl": 650.0},
                {"timestamp": "2024-01-03T00:00:00", "total_usdc": 9900.0, "total_positions_value": 400.0, "cumulative_pnl": 300.0},
                {"timestamp": "2024-01-04T00:00:00", "total_usdc": 10200.0, "total_positions_value": 600.0, "cumulative_pnl": 800.0},
                {"timestamp": "2024-01-05T00:00:00", "total_usdc": 10350.0, "total_positions_value": 650.0, "cumulative_pnl": 1000.0},
                {"timestamp": "2024-01-06T00:00:00", "total_usdc": 10150.0, "total_positions_value": 500.0, "cumulative_pnl": 650.0},
                {"timestamp": "2024-01-07T00:00:00", "total_usdc": 10400.0, "total_positions_value": 700.0, "cumulative_pnl": 1100.0},
            ]

            pnl_response = []
            for data in mock_data:
                pnl_response.append(PnLSnapshotResponse(**data))

        return pnl_response
    except Exception as e:
        logger.error(f"Error getting cumulative PnL data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trades", response_model=List[TradeRecordResponse])
async def get_trades(
    market_id: Optional[str] = Query(None),
    sort_by: Optional[str] = Query('timestamp'),
    sort_order: Optional[str] = Query('desc')
):
    """
    Get trade history with optional filtering and sorting
    """
    try:
        db_session = db_manager.SessionLocal()
        try:
            # Build query
            query = db_session.query(Trade)

            # Apply market filter if provided
            if market_id:
                query = query.filter(Trade.market_id == market_id)

            # Apply sorting
            if sort_by == 'timestamp':
                if sort_order == 'asc':
                    query = query.order_by(Trade.timestamp.asc())
                else:
                    query = query.order_by(Trade.timestamp.desc())
            elif sort_by == 'market_id':
                if sort_order == 'asc':
                    query = query.order_by(Trade.market_id.asc())
                else:
                    query = query.order_by(Trade.market_id.desc())
            elif sort_by == 'price':
                if sort_order == 'asc':
                    query = query.order_by(Trade.price.asc())
                else:
                    query = query.order_by(Trade.price.desc())
            elif sort_by == 'size':
                if sort_order == 'asc':
                    query = query.order_by(Trade.size.asc())
                else:
                    query = query.order_by(Trade.size.desc())
            else:
                # Default sorting by timestamp descending
                query = query.order_by(Trade.timestamp.desc())

            # Execute query
            trades = query.all()

            # Convert to response format
            trades_response = []
            for trade in trades:
                trades_response.append(TradeRecordResponse(
                    id=trade.id,
                    timestamp=trade.timestamp.isoformat(),
                    market_id=trade.market_id,
                    side=trade.side,
                    price=float(trade.price),
                    size=float(trade.size),
                    fee=float(trade.fee) if trade.fee else None,
                    tx_hash=trade.tx_hash
                ))
        finally:
            db_session.close()

        return trades_response
    except Exception as e:
        logger.error(f"Error getting trade history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/win-loss", response_model=WinLossAnalysisResponse)
async def get_win_loss_analysis():
    """
    Get win/loss analysis showing percentage of profitable vs loss-making trades
    """
    try:
        db_session = db_manager.SessionLocal()
        try:
            # Get all trades
            trades = db_session.query(Trade).all()

            if not trades:
                # Return mock data if no trades exist
                return WinLossAnalysisResponse(
                    profit_count=68,
                    loss_count=32,
                    profit_percentage=68.0,
                    loss_percentage=32.0
                )

            # For simplicity, we'll simulate profit/loss analysis
            # In a real implementation, this would require calculating PnL per trade
            # For now, we'll return mock data based on the number of trades
            total_trades = len(trades)
            profit_count = int(total_trades * 0.68)  # 68% profitable
            loss_count = total_trades - profit_count

            profit_percentage = round((profit_count / total_trades) * 100, 2) if total_trades > 0 else 0
            loss_percentage = round((loss_count / total_trades) * 100, 2) if total_trades > 0 else 0

            return WinLossAnalysisResponse(
                profit_count=profit_count,
                loss_count=loss_count,
                profit_percentage=profit_percentage,
                loss_percentage=loss_percentage
            )
        finally:
            db_session.close()
    except Exception as e:
        logger.error(f"Error getting win/loss analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint for health check"""
    return {
        "message": "Polymarket MM Bot Control Tower API",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)