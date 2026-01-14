"""
Configuration Manager for Polymarket MM Bot
Handles dynamic configuration updates through the database
"""
from decimal import Decimal
from typing import Optional
from .database import db_manager
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Manages bot configuration parameters that can be updated dynamically
    """
    
    def __init__(self):
        # Initialize default values in the database if they don't exist
        self.initialize_defaults()
    
    def initialize_defaults(self):
        """Initialize default configuration values in the database"""
        defaults = [
            {"param_name": "target_spread", "param_value": "0.0020", "description": "Target spread for market making (20 bps)"},
            {"param_name": "max_exposure", "param_value": "1000", "description": "Maximum exposure per market ($1000)"},
            {"param_name": "min_order_size", "param_value": "10", "description": "Minimum order size"},
            {"param_name": "max_order_size", "param_value": "1000", "description": "Maximum order size"},
            {"param_name": "kill_switch_threshold", "param_value": "0.10", "description": "Kill switch threshold (10% loss)"},
            {"param_name": "fat_finger_threshold", "param_value": "0.05", "description": "Fat finger check threshold (5% deviation)"},
        ]
        
        for default in defaults:
            existing = db_manager.get_bot_config(default["param_name"])
            if not existing:
                db_manager.save_bot_config(
                    param_name=default["param_name"],
                    param_value=default["param_value"],
                    description=default["description"]
                )
    
    def get_target_spread(self) -> Decimal:
        """Get the target spread from database"""
        config = db_manager.get_bot_config("target_spread")
        if config:
            return Decimal(config.param_value)
        return Decimal('0.0020')  # Default 20 bps
    
    def set_target_spread(self, value: Decimal) -> bool:
        """Set the target spread in database"""
        try:
            db_manager.save_bot_config(
                param_name="target_spread",
                param_value=str(value),
                description="Target spread for market making"
            )
            logger.info(f"Updated target spread to {value}")
            return True
        except Exception as e:
            logger.error(f"Error updating target spread: {str(e)}")
            return False
    
    def get_max_exposure(self) -> Decimal:
        """Get the max exposure from database"""
        config = db_manager.get_bot_config("max_exposure")
        if config:
            return Decimal(config.param_value)
        return Decimal('1000')  # Default $1000
    
    def set_max_exposure(self, value: Decimal) -> bool:
        """Set the max exposure in database"""
        try:
            db_manager.save_bot_config(
                param_name="max_exposure",
                param_value=str(value),
                description="Maximum exposure per market"
            )
            logger.info(f"Updated max exposure to {value}")
            return True
        except Exception as e:
            logger.error(f"Error updating max exposure: {str(e)}")
            return False
    
    def get_min_order_size(self) -> Decimal:
        """Get the min order size from database"""
        config = db_manager.get_bot_config("min_order_size")
        if config:
            return Decimal(config.param_value)
        return Decimal('10')  # Default 10
    
    def set_min_order_size(self, value: Decimal) -> bool:
        """Set the min order size in database"""
        try:
            db_manager.save_bot_config(
                param_name="min_order_size",
                param_value=str(value),
                description="Minimum order size"
            )
            logger.info(f"Updated min order size to {value}")
            return True
        except Exception as e:
            logger.error(f"Error updating min order size: {str(e)}")
            return False
    
    def get_max_order_size(self) -> Decimal:
        """Get the max order size from database"""
        config = db_manager.get_bot_config("max_order_size")
        if config:
            return Decimal(config.param_value)
        return Decimal('1000')  # Default 1000
    
    def set_max_order_size(self, value: Decimal) -> bool:
        """Set the max order size in database"""
        try:
            db_manager.save_bot_config(
                param_name="max_order_size",
                param_value=str(value),
                description="Maximum order size"
            )
            logger.info(f"Updated max order size to {value}")
            return True
        except Exception as e:
            logger.error(f"Error updating max order size: {str(e)}")
            return False
    
    def get_kill_switch_threshold(self) -> Decimal:
        """Get the kill switch threshold from database"""
        config = db_manager.get_bot_config("kill_switch_threshold")
        if config:
            return Decimal(config.param_value)
        return Decimal('0.10')  # Default 10%
    
    def set_kill_switch_threshold(self, value: Decimal) -> bool:
        """Set the kill switch threshold in database"""
        try:
            db_manager.save_bot_config(
                param_name="kill_switch_threshold",
                param_value=str(value),
                description="Kill switch threshold (percentage)"
            )
            logger.info(f"Updated kill switch threshold to {value}")
            return True
        except Exception as e:
            logger.error(f"Error updating kill switch threshold: {str(e)}")
            return False
    
    def get_fat_finger_threshold(self) -> Decimal:
        """Get the fat finger threshold from database"""
        config = db_manager.get_bot_config("fat_finger_threshold")
        if config:
            return Decimal(config.param_value)
        return Decimal('0.05')  # Default 5%
    
    def set_fat_finger_threshold(self, value: Decimal) -> bool:
        """Set the fat finger threshold in database"""
        try:
            db_manager.save_bot_config(
                param_name="fat_finger_threshold",
                param_value=str(value),
                description="Fat finger check threshold (percentage)"
            )
            logger.info(f"Updated fat finger threshold to {value}")
            return True
        except Exception as e:
            logger.error(f"Error updating fat finger threshold: {str(e)}")
            return False


# Global config manager instance
config_manager = ConfigManager()