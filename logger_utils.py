"""
日誌工具模組
提供統一的日誌管理功能
"""

import logging


# ==============================
# 日誌配置
# ==============================
class Logger:
    """統一的日誌管理器"""
    def __init__(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def info(self, msg): 
        self.logger.info(msg)
    
    def warning(self, msg): 
        self.logger.warning(msg)
    
    def error(self, msg): 
        self.logger.error(msg)
    
    def critical(self, msg): 
        self.logger.critical(msg)


# 全局日誌實例
logger = Logger()