"""
程式進入點
優化版無人機航線規劃工具的主要啟動文件
"""

from tkinter import messagebox

from logger_utils import logger
from main_app import DronePathPlannerApp


# ==============================
# 程式進入點
# ==============================
def main():
    """主函式"""
    try:
        # 建立應用程式
        app = DronePathPlannerApp()
        
        # 執行主迴圈
        logger.info("優化版無人機航線規劃工具啟動成功")
        app.mainloop()
        
    except Exception as e:
        logger.critical(f"程式啟動失敗: {e}")
        messagebox.showerror("啟動錯誤", f"程式啟動失敗: {str(e)}")
    finally:
        logger.info("程式已退出")


if __name__ == '__main__':
    main()