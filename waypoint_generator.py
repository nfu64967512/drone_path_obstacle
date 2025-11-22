"""
優化航點生成器模組
負責生成完整的任務航點，包含網格掃描、返回綠色起點、RTL等功能
"""

import math
from typing import List, Tuple, Optional

from config import Config, FlightParameters
from collision_avoidance import CollisionAvoidanceSystem
from logger_utils import logger


# ==============================
# 優化航點生成器
# ==============================
class OptimizedWaypointGenerator:
    """優化後的航點生成器 - 整合智能避撞和完整任務循環"""
    
    def __init__(self):
        self.collision_avoidance = CollisionAvoidanceSystem(Config.SAFETY_DISTANCE_M)
        self.earth_radius_m = 111111.0
    
    def generate_complete_mission(self, corners: List[Tuple[float, float]], 
                                 params: FlightParameters, 
                                 region_idx: int,
                                 total_regions: int,
                                 start_from_left: bool = True,
                                 loiter_time: float = 0.0) -> Tuple[List[str], List[Tuple[float, float]]]:
        """
        生成完整任務航點：
        1. 網格掃描
        2. 返回綠色起點
        3. RTL with 高度錯開
        """
        try:
            # 生成基本網格航點
            lines, waypoints = self.generate_grid_waypoints(
                corners, params, start_from_left)
            
            if not waypoints:
                return lines, waypoints
            
            # 插入LOITER命令（如果需要）
            if loiter_time > 0:
                lines = self.collision_avoidance.insert_loiter_command(
                    lines, loiter_time, insert_after_line=2)
            
            # 添加返回起點的航點
            first_waypoint = waypoints[0]
            return_line = f"{len(lines)-1}\t0\t3\t16\t0\t0\t0\t0\t{first_waypoint[0]:.6f}\t{first_waypoint[1]:.6f}\t{params.altitude:.2f}\t1"
            lines.insert(-1, return_line)  # 插入在最後減速命令前
            waypoints.append(first_waypoint)
            
            # 計算RTL高度（錯開返航）
            rtl_altitude = self.calculate_rtl_altitude(
                params.altitude, region_idx, total_regions)
            
            # 添加RTL命令與高度設定
            seq = len(lines) - 1
            lines.insert(-1, f"{seq}\t0\t3\t178\t0\t5.0\t0\t0\t0\t0\t0\t1")  # 減速至5m/s
            seq += 1
            lines.insert(-1, f"{seq}\t0\t3\t22\t0\t0\t0\t0\t0\t0\t{rtl_altitude:.1f}\t1")  # TAKEOFF到RTL高度
            seq += 1
            lines.insert(-1, f"{seq}\t0\t3\t20\t0\t0\t0\t0\t0\t0\t0\t1")  # RTL命令
            
            # 更新序列號
            lines = self.update_all_sequence_numbers(lines)
            
            return lines, waypoints
            
        except Exception as e:
            logger.error(f"生成完整任務失敗: {e}")
            return ["QGC WPL 110"], []
    
    def calculate_rtl_altitude(self, base_altitude: float, 
                              region_idx: int, total_regions: int) -> float:
        """
        計算RTL高度，實現高度錯開
        區域1: base + 9m
        區域2: base + 6m
        區域3: base + 3m
        區域4: base + 0m
        """
        altitude_offset = (total_regions - region_idx - 1) * Config.RTL_ALTITUDE_INCREMENT
        return base_altitude + altitude_offset
    
    def generate_grid_waypoints(self, corners: List[Tuple[float, float]], 
                              params: FlightParameters,
                              start_from_left: bool = True) -> Tuple[List[str], List[Tuple[float, float]]]:
        """生成網格掃描航點"""
        try:
            # 座標變換
            pts_rot, lat0, lon0, cosLat0, cos_t, sin_t = self.project_and_rotate(
                corners, params.angle)
            
            if not pts_rot:
                return ["QGC WPL 110"], []
            
            # 計算掃描線
            ys = [p[1] for p in pts_rot]
            minY, maxY = min(ys), max(ys)
            
            # 確保完全覆蓋
            margin = params.spacing * 0.1
            minY -= margin
            maxY += margin
            
            total_lines = max(1, int(math.ceil((maxY - minY) / params.spacing)) + 1)
            
            # 開始生成航點文件
            lines = ["QGC WPL 110"]
            seq = 0
            
            # HOME點
            lines.append(f"{seq}\t0\t3\t179\t0\t0\t0\t0\t0\t0\t0\t1")
            seq += 1
            
            # 速度設定
            lines.append(f"{seq}\t0\t3\t178\t0\t{params.speed:.1f}\t0\t0\t0\t0\t0\t1")
            seq += 1
            
            waypoints = []
            prev_lat, prev_lon = None, None
            
            for li in range(total_lines):
                y = minY + li * params.spacing
                if y > maxY:
                    y = maxY
                
                # 計算與多邊形的交點
                xs = self.intersect_line_polygon(pts_rot, y)
                
                if len(xs) < 2:
                    continue
                
                # 確定掃描方向（之字形）
                go_left_to_right = (li % 2 == 0) if start_from_left else (li % 2 == 1)
                
                if go_left_to_right:
                    line_points = [(xs[0], y), (xs[-1], y)]
                else:
                    line_points = [(xs[-1], y), (xs[0], y)]
                
                # 轉換回地理座標並生成航點
                for xr, yr in line_points:
                    lat, lon = self.rotate_back_to_geographic(
                        cos_t, sin_t, xr, yr, lat0, lon0, cosLat0)
                    
                    waypoints.append((lat, lon))
                    
                    # 加入轉向指令（除了第一個點）
                    if prev_lat is not None:
                        bearing = self.calculate_bearing(prev_lat, prev_lon, lat, lon)
                        lines.append(f"{seq}\t0\t3\t115\t{bearing:.1f}\t{params.yaw_speed:.1f}\t0\t0\t0\t0\t0\t1")
                        seq += 1
                    
                    # 加入航點
                    lines.append(f"{seq}\t0\t3\t16\t0\t0\t0\t0\t{lat:.6f}\t{lon:.6f}\t{params.altitude:.2f}\t1")
                    seq += 1
                    
                    prev_lat, prev_lon = lat, lon
            
            # 最後減速
            lines.append(f"{seq}\t0\t3\t178\t0\t10.0\t0\t0\t0\t0\t0\t0\t1")
            
            return lines, waypoints
        
        except Exception as e:
            logger.error(f"生成航點錯誤: {e}")
            return ["QGC WPL 110"], []
    
    def update_all_sequence_numbers(self, lines: List[str]) -> List[str]:
        """更新所有序列號"""
        updated_lines = []
        seq = 0
        
        for line in lines:
            if line.startswith('#') or line == "QGC WPL 110":
                updated_lines.append(line)
            else:
                parts = line.split('\t')
                if len(parts) > 0:
                    parts[0] = str(seq)
                    updated_lines.append('\t'.join(parts))
                    seq += 1
        
        return updated_lines
    
    def calculate_bearing(self, lat1: float, lon1: float, 
                        lat2: float, lon2: float) -> float:
        """計算兩點間的方位角"""
        dLon = math.radians(lon2 - lon1)
        lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
        
        x = math.sin(dLon) * math.cos(lat2_rad)
        y = (math.cos(lat1_rad) * math.sin(lat2_rad) - 
             math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dLon))
        
        bearing = math.degrees(math.atan2(x, y))
        return (bearing + 360) % 360
    
    def project_and_rotate(self, corners: List[Tuple[float, float]], angle_deg: float):
        """投影和旋轉座標系"""
        # 計算中心點
        lat0 = sum(p[0] for p in corners) / len(corners)
        lon0 = sum(p[1] for p in corners) / len(corners)
        cosLat0 = math.cos(math.radians(lat0))
        
        # 旋轉角度
        theta = math.radians(angle_deg)
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        
        # 投影並旋轉每個點
        pts_rot = []
        for lat, lon in corners:
            x = (lon - lon0) * Config.EARTH_RADIUS_M * cosLat0
            y = (lat - lat0) * Config.EARTH_RADIUS_M
            
            xr = cos_t * x - sin_t * y
            yr = sin_t * x + cos_t * y
            pts_rot.append((xr, yr))
        
        return pts_rot, lat0, lon0, cosLat0, cos_t, sin_t
    
    def intersect_line_polygon(self, pts: List[Tuple[float, float]], y: float) -> List[float]:
        """計算水平線與多邊形的交點"""
        xs = []
        n = len(pts)
        
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            
            # 檢查線段是否與水平線相交
            if (y1 <= y <= y2) or (y2 <= y <= y1):
                if abs(y2 - y1) > 1e-10:
                    t = (y - y1) / (y2 - y1)
                    x_intersect = x1 + t * (x2 - x1)
                    xs.append(x_intersect)
        
        return sorted(xs)
    
    def rotate_back_to_geographic(self, cos_t: float, sin_t: float, xr: float, yr: float, 
                                lat0: float, lon0: float, cosLat0: float) -> Tuple[float, float]:
        """從旋轉座標系轉回地理座標"""
        # 反旋轉
        x = cos_t * xr + sin_t * yr
        y = -sin_t * xr + cos_t * yr
        
        # 反投影到地理座標
        lat = y / Config.EARTH_RADIUS_M + lat0
        lon = x / (Config.EARTH_RADIUS_M * cosLat0) + lon0
        
        return lat, lon