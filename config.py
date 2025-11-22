"""
配置常數和資料類
包含應用程式的所有配置參數和資料結構定義
"""

from dataclasses import dataclass
from typing import List, Tuple


# ==============================
# 配置常數
# ==============================
class Config:
    """應用程式配置常數"""
    # 界面配置
    WINDOW_TITLE = "無人機網格航線規劃工具"
    WINDOW_SIZE = "1600x1000"
    MIN_WINDOW_SIZE = (1000, 700)
    
    # 地圖配置
    DEFAULT_POSITION = (23.702732, 120.419333)
    DEFAULT_ZOOM = 16
    MAP_SERVERS = [
        ("Google衛星", "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", 22),
        ("OpenStreetMap", "https://tile.openstreetmap.org/{z}/{x}/{y}.png", 19),
        ("Google地圖", "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}", 22)
    ]
    
    # 路徑樣式
    PATH_WIDTH_DEFAULT = 4
    PATH_COLORS = ["#08EC91", "#2DB7F5", "#F76560", "#F7BA1E",
                   "#8A2BE2", "#00C2B8", "#FF8F1F", "#6C8CFF"]
    
    # 區域樣式
    REGION_BORDER_WIDTH = 2
    REGION_BORDER_COLOR = "#6aa84f"
    REGION_FILL_COLORS = [
        "#cfe8cf", "#cfe3f6", "#ffd9d6", "#fbe7c3",
        "#e3d7f7", "#d5f3ef", "#ffe4cc", "#dee4ff"
    ]
    
    # 標記樣式
    START_MARKER_COLOR = "#00FF00"  # 綠色起點
    END_MARKER_COLOR = "#FF0000"    # 紅色終點
    WAYPOINT_MARKER_COLOR = "#0080FF"  # 藍色航點
    
    # 邊界點限制
    MAX_CORNERS = 10
    MIN_CORNERS = 3
    
    # 地球半徑（公尺/度）
    EARTH_RADIUS_M = 111111.0
    
    # 安全參數
    SAFETY_DISTANCE_M = 5.0  # 安全間距5公尺
    RTL_ALTITUDE_INCREMENT = 3.0  # RTL高度遞增值


# ==============================
# 飛行動力學參數
# ==============================
@dataclass
class FlightDynamics:
    """飛行動力學參數"""
    max_acceleration: float = 2.0      # 最大加速度 [m/s²]
    max_deceleration: float = 2.5      # 最大減速度 [m/s²] 
    max_yaw_acceleration: float = 45.0 # 最大轉向加速度 [deg/s²]
    hover_time: float = 2.0            # 航點懸停時間 [s]
    takeoff_time: float = 5.0          # 起飛時間 [s]
    landing_time: float = 3.0          # 降落時間 [s]
    min_turn_radius: float = 2.0       # 最小轉彎半徑 [m]
    wind_factor: float = 1.1           # 風阻係數
    safety_buffer: float = 10.0        # 安全緩衝時間 [s]
    
    # 速度調整係數
    large_turn_speed_factor: float = 0.7    # 大角度轉向速度係數（45-90度）
    sharp_turn_speed_factor: float = 0.5    # 銳角轉向速度係數（90-135度）
    uturn_speed_factor: float = 0.3         # U型轉向速度係數（135度以上）


@dataclass
class FlightParameters:
    """飛行參數資料類"""
    altitude: float
    angle: float
    spacing: float
    speed: float
    yaw_speed: float
    safety_distance: float = 5.0  # 預設5公尺安全間距

    def validate(self) -> bool:
        """驗證參數有效性"""
        if self.altitude <= 0: 
            raise ValueError("飛行高度必須大於0")
        if self.spacing <= 0: 
            raise ValueError("航線間距必須大於0")
        if self.speed <= 0: 
            raise ValueError("飛行速度必須大於0")
        if self.yaw_speed <= 0: 
            raise ValueError("轉向速度必須大於0")
        if not -180 <= self.angle <= 180: 
            raise ValueError("角度必須在-180到180度之間")
        if self.safety_distance < 0:
            raise ValueError("安全間距不能為負數")
        return True