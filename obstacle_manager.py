"""
障礙物管理器模組 - 智能網格線分段版
實現方案一：網格線智能分段避障，最大化偵察覆蓋率
"""

import math
from typing import List, Tuple, Optional
from logger_utils import logger

try:
    from config import Config
except ImportError:
    class Config:
        EARTH_RADIUS_M = 6378137.0

class Obstacle:
    """障礙物資料類"""
    def __init__(self, center: Tuple[float, float], radius: float, safe_distance: float = 1.0):
        self.center = center  # (lat, lon)
        self.radius = radius  # 公尺
        self.safe_distance = safe_distance  # 安全距離（公尺）
        self.marker = None  # 地圖標記
        self.circle = None  # 圓形顯示
        self.safe_circle = None # 安全範圍顯示
        
    @property
    def effective_radius(self):
        """有效半徑 = 障礙物半徑 + 安全距離"""
        return self.radius + self.safe_distance


class ObstacleManager:
    """
    障礙物管理器 - 智能網格線分段版
    
    核心功能：
    1. 識別網格掃描線結構
    2. 檢測掃描線是否穿過障礙物
    3. 將穿過障礙物的掃描線分段
    4. 生成繞行路徑，保持最大偵察覆蓋率
    """
    
    def __init__(self):
        self.obstacles: List[Obstacle] = []
        self.earth_radius_m = 111111.0  # 每度約111111公尺
        
    def add_obstacle(self, center: Tuple[float, float], radius: float, 
                    safe_distance: float = 1.0) -> Obstacle:
        """添加障礙物"""
        obstacle = Obstacle(center, radius, safe_distance)
        self.obstacles.append(obstacle)
        logger.info(f"添加障礙物：中心{center}, 半徑{radius}m, 安全距離{safe_distance}m")
        return obstacle
    
    def remove_obstacle(self, obstacle: Obstacle):
        """移除障礙物"""
        if obstacle in self.obstacles:
            self.obstacles.remove(obstacle)
            logger.info(f"移除障礙物：{obstacle.center}")
            return True
        return False

    def remove_nearest_obstacle(self, coords: Tuple[float, float], threshold_m: float = 50.0):
        """移除指定座標最近的障礙物"""
        if not self.obstacles:
            return None
            
        nearest_obs = None
        min_dist = float('inf')
        
        for obs in self.obstacles:
            dist = self.calculate_distance(coords, obs.center)
            if dist < min_dist:
                min_dist = dist
                nearest_obs = obs
                
        if nearest_obs:
            self.remove_obstacle(nearest_obs)
            return nearest_obs
        return None
    
    def clear_all(self):
        """清除所有障礙物"""
        self.obstacles.clear()
        logger.info("清除所有障礙物")

    def filter_waypoints_with_detour(self, waypoints: List[Tuple[float, float]], 
                                     boundary_corners: List[Tuple[float, float]] = None) -> List[Tuple[float, float]]:
        """
        智能網格線分段避障演算法（方案一）
        
        流程：
        1. 識別掃描線段（通過距離分析）
        2. 檢測掃描線是否穿過障礙物
        3. 如果穿過，將線段智能分段：前段 + 繞行段 + 後段
        4. 保持最大偵察覆蓋率
        """
        if not waypoints or not self.obstacles:
            return waypoints

        # 識別掃描線段結構
        scan_segments = self._identify_scan_segments(waypoints)
        
        result_waypoints = []
        processed_indices = set()
        
        for seg_type, indices in scan_segments:
            if seg_type == "scan":
                # 這是一條掃描線段
                start_idx, end_idx = indices
                p1 = waypoints[start_idx]
                p2 = waypoints[end_idx]
                
                # 檢查是否穿過障礙物
                colliding_obstacles = self.check_segment_collision(p1, p2)
                
                if not colliding_obstacles:
                    # 無障礙物，正常添加掃描線兩端點
                    if start_idx not in processed_indices:
                        result_waypoints.append(p1)
                        processed_indices.add(start_idx)
                    if end_idx not in processed_indices:
                        result_waypoints.append(p2)
                        processed_indices.add(end_idx)
                else:
                    # 有障礙物，智能分段處理
                    segmented_waypoints = self._segment_scan_line(p1, p2, colliding_obstacles, boundary_corners)
                    
                    # 添加分段後的航點（去重）
                    for wp in segmented_waypoints:
                        if wp not in result_waypoints:
                            result_waypoints.append(wp)
                    
                    processed_indices.add(start_idx)
                    processed_indices.add(end_idx)
                    logger.info(f"掃描線 {start_idx}-{end_idx} 穿過障礙物，已分段處理，生成{len(segmented_waypoints)}個航點")
            
            elif seg_type == "turn":
                # 轉向段，直接添加未處理的點
                for idx in indices:
                    if idx not in processed_indices:
                        result_waypoints.append(waypoints[idx])
                        processed_indices.add(idx)
        
        # 確保所有未處理的點都被添加
        for i, wp in enumerate(waypoints):
            if i not in processed_indices:
                result_waypoints.append(wp)
                processed_indices.add(i)
        
        return result_waypoints
    
    def _identify_scan_segments(self, waypoints: List[Tuple[float, float]]) -> List[Tuple[str, Tuple[int, int]]]:
        """
        識別掃描線段結構
        
        基於距離分析：
        - 長距離段（>閾值）：掃描線
        - 短距離段（<閾值）：轉向段
        
        返回: [(segment_type, (start_index, end_index)), ...]
        segment_type: "scan" 或 "turn"
        """
        if len(waypoints) < 2:
            return []
        
        segments = []
        
        # 計算所有相鄰點之間的距離
        distances = []
        for i in range(len(waypoints) - 1):
            dist = self.calculate_distance(waypoints[i], waypoints[i + 1])
            distances.append((i, i + 1, dist))
        
        if not distances:
            return []
        
        # 找出距離中位數作為閾值
        sorted_dists = sorted([d[2] for d in distances])
        median_dist = sorted_dists[len(sorted_dists) // 2]
        
        # 閾值：中位數的60%
        # 大於閾值的是掃描線，小於閾值的是轉向段
        threshold = median_dist * 0.6
        
        # 識別掃描線段
        for idx_start, idx_end, dist in distances:
            if dist > threshold:
                segments.append(("scan", (idx_start, idx_end)))
            else:
                segments.append(("turn", (idx_start, idx_end)))
        
        logger.info(f"識別掃描結構：{len([s for s in segments if s[0]=='scan'])}條掃描線，閾值={threshold:.2f}m")
        return segments
    
    def _segment_scan_line(self, p1: Tuple[float, float], p2: Tuple[float, float],
                          obstacles: List[Obstacle], 
                          boundary_corners: Optional[List[Tuple[float, float]]]) -> List[Tuple[float, float]]:
        """
        將穿過障礙物的掃描線分段
        
        策略：
        1. 計算掃描線與障礙物的交點
        2. 生成繞行路徑（沿著障礙物安全邊界）
        3. 返回: [p1, 進入繞行點, 離開繞行點, p2]
        
        返回: 分段後的航點列表
        """
        # 處理第一個障礙物（如果有多個，優先處理最接近起點的）
        obstacle = obstacles[0]
        
        # 計算線段與圓的交點
        intersection_points = self._calculate_line_circle_intersection(p1, p2, obstacle)
        
        if len(intersection_points) < 2:
            # 沒有足夠的交點，可能只是擦過，返回原始線段
            return [p1, p2]
        
        # 生成繞行路徑（沿著障礙物安全邊界的切線）
        detour_points = self._generate_tangent_detour(p1, p2, obstacle, intersection_points[0], intersection_points[1])
        
        # 驗證繞行點是否在邊界內
        valid_detour = []
        for dp in detour_points:
            if boundary_corners is None or self.point_in_polygon(dp, boundary_corners):
                valid_detour.append(dp)
        
        if not valid_detour:
            # 無法生成有效繞行路徑，返回原始線段
            logger.warning("無法生成有效繞行路徑，保留原始線段")
            return [p1, p2]
        
        # 返回完整的分段路徑：起點 → 繞行點 → 終點
        return [p1] + valid_detour + [p2]
    
    def _calculate_line_circle_intersection(self, p1: Tuple[float, float], 
                                           p2: Tuple[float, float],
                                           obstacle: Obstacle) -> List[Tuple[float, float]]:
        """
        計算線段與圓形障礙物的交點
        
        使用參數方程：
        - 線段: P(t) = P1 + t(P2 - P1), t ∈ [0, 1]
        - 圓: (x - cx)² + (y - cy)² = r²
        
        返回: 交點列表（地理座標）
        """
        lat1, lon1 = p1
        lat2, lon2 = p2
        cx, cy = obstacle.center
        radius = obstacle.effective_radius
        
        # 轉換為米制座標
        avg_lat_rad = math.radians(cx)
        cos_lat = math.cos(avg_lat_rad)
        
        def to_meters(lat, lon):
            y = (lat - cx) * (math.pi / 180) * self.earth_radius_m
            x = (lon - cy) * (math.pi / 180) * self.earth_radius_m * cos_lat
            return x, y
        
        def to_latlon(x, y):
            lat = cx + y / self.earth_radius_m * (180 / math.pi)
            lon = cy + x / (self.earth_radius_m * cos_lat) * (180 / math.pi)
            return lat, lon
        
        x1, y1 = to_meters(lat1, lon1)
        x2, y2 = to_meters(lat2, lon2)
        
        # 線段參數方程
        dx = x2 - x1
        dy = y2 - y1
        
        # 代入圓方程，得到二次方程 at² + bt + c = 0
        a = dx * dx + dy * dy
        b = 2 * (dx * x1 + dy * y1)
        c = x1 * x1 + y1 * y1 - radius * radius
        
        discriminant = b * b - 4 * a * c
        
        if discriminant < 0 or a == 0:
            return []  # 無交點
        
        # 計算兩個解
        t1 = (-b - math.sqrt(discriminant)) / (2 * a)
        t2 = (-b + math.sqrt(discriminant)) / (2 * a)
        
        # 篩選在線段上的交點 (0 <= t <= 1)
        intersections = []
        for t in [t1, t2]:
            if 0 <= t <= 1:
                x = x1 + t * dx
                y = y1 + t * dy
                intersections.append(to_latlon(x, y))
        
        return intersections
    
    def _generate_tangent_detour(self, p1: Tuple[float, float], p2: Tuple[float, float],
                                 obstacle: Obstacle,
                                 inter1: Tuple[float, float], 
                                 inter2: Tuple[float, float]) -> List[Tuple[float, float]]:
        """
        生成沿著障礙物邊界的繞行路徑（切線法）
        
        策略：
        1. 計算掃描線方向
        2. 確定繞行方向（左側或右側）
        3. 在障礙物圓周上選擇繞行點
        4. 確保繞行點在安全範圍外
        
        返回: [進入繞行點, 離開繞行點]
        """
        cx, cy = obstacle.center
        radius = obstacle.effective_radius * 1.2  # 增加20%安全邊距
        
        # 轉換為米制座標系統
        avg_lat_rad = math.radians(cx)
        cos_lat = math.cos(avg_lat_rad)
        
        def to_meters(lat, lon):
            y = (lat - cx) * (math.pi / 180) * self.earth_radius_m
            x = (lon - cy) * (math.pi / 180) * self.earth_radius_m * cos_lat
            return x, y
        
        def to_latlon(x, y):
            lat = cx + y / self.earth_radius_m * (180 / math.pi)
            lon = cy + x / (self.earth_radius_m * cos_lat) * (180 / math.pi)
            return lat, lon
        
        # 計算掃描線的方向向量
        x1, y1 = to_meters(p1[0], p1[1])
        x2, y2 = to_meters(p2[0], p2[1])
        
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx * dx + dy * dy)
        
        if length < 0.001:
            return []
        
        # 單位方向向量
        ux = dx / length
        uy = dy / length
        
        # 計算垂直向量（用於決定繞行方向）
        perp_x = -uy  # 向左垂直
        perp_y = ux
        
        # 生成兩個候選繞行方向
        detour_offset = radius
        
        # 方向1：左側繞行
        detour1_x = perp_x * detour_offset
        detour1_y = perp_y * detour_offset
        
        # 方向2：右側繞行
        detour2_x = -perp_x * detour_offset
        detour2_y = -perp_y * detour_offset
        
        # 選擇距離原點較近的繞行方向（簡化選擇邏輯）
        dist1_sq = detour1_x ** 2 + detour1_y ** 2
        dist2_sq = detour2_x ** 2 + detour2_y ** 2
        
        if dist1_sq < dist2_sq:
            detour_x, detour_y = detour1_x, detour1_y
        else:
            detour_x, detour_y = detour2_x, detour2_y
        
        # 生成進入和離開繞行的航點
        # 在掃描線的25%和75%位置設置繞行點
        t_entry = 0.25
        t_exit = 0.75
        
        entry_x = x1 + ux * length * t_entry + detour_x
        entry_y = y1 + uy * length * t_entry + detour_y
        
        exit_x = x1 + ux * length * t_exit + detour_x
        exit_y = y1 + uy * length * t_exit + detour_y
        
        # 轉換回地理座標
        entry_point = to_latlon(entry_x, entry_y)
        exit_point = to_latlon(exit_x, exit_y)
        
        return [entry_point, exit_point]
    
    def point_in_polygon(self, point: Tuple[float, float], 
                        polygon: List[Tuple[float, float]]) -> bool:
        """射線法判斷點是否在多邊形內"""
        lat, lon = point
        n = len(polygon)
        inside = False
        
        p1_lat, p1_lon = polygon[0]
        for i in range(1, n + 1):
            p2_lat, p2_lon = polygon[i % n]
            if lon > min(p1_lon, p2_lon):
                if lon <= max(p1_lon, p2_lon):
                    if lat <= max(p1_lat, p2_lat):
                        if p1_lon != p2_lon:
                            xinters = (lon - p1_lon) * (p2_lat - p1_lat) / (p2_lon - p1_lon) + p1_lat
                        if p1_lat == p2_lat or lat <= xinters:
                            inside = not inside
            p1_lat, p1_lon = p2_lat, p2_lon
        
        return inside
    
    def check_waypoint_collision(self, waypoint: Tuple[float, float]) -> bool:
        """檢查航點是否與任何障礙物衝突"""
        for obstacle in self.obstacles:
            distance = self.calculate_distance(waypoint, obstacle.center)
            if distance < obstacle.effective_radius:
                return True
        return False
    
    def check_segment_collision(self, p1: Tuple[float, float], 
                               p2: Tuple[float, float]) -> List[Obstacle]:
        """
        檢查線段是否穿過障礙物
        返回: 與線段碰撞的障礙物列表
        """
        colliding_obstacles = []
        for obstacle in self.obstacles:
            if self.line_intersects_circle(p1, p2, obstacle.center, 
                                          obstacle.effective_radius):
                colliding_obstacles.append(obstacle)
        return colliding_obstacles
    
    def calculate_distance(self, p1: Tuple[float, float], 
                          p2: Tuple[float, float]) -> float:
        """計算兩點間距離（公尺）- 平面近似"""
        lat1, lon1 = p1
        lat2, lon2 = p2
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        avg_lat = math.radians((lat1 + lat2) / 2)
        
        x = dlon * math.cos(avg_lat)
        y = dlat
        distance = math.sqrt(x*x + y*y) * self.earth_radius_m
        return distance
    
    def line_intersects_circle(self, p1: Tuple[float, float], 
                               p2: Tuple[float, float],
                               center: Tuple[float, float], 
                               radius_m: float) -> bool:
        """
        檢測線段是否與圓相交
        
        使用點到線段的最短距離算法
        """
        lat1, lon1 = p1
        lat2, lon2 = p2
        cx, cy = center
        
        avg_lat_rad = math.radians(cx)
        cos_lat = math.cos(avg_lat_rad)
        
        def to_meters(lat, lon):
            y = (lat - cx) * (math.pi / 180) * self.earth_radius_m
            x = (lon - cy) * (math.pi / 180) * self.earth_radius_m * cos_lat
            return x, y

        x1, y1 = to_meters(lat1, lon1)
        x2, y2 = to_meters(lat2, lon2)
        
        dx = x2 - x1
        dy = y2 - y1
        dr2 = dx*dx + dy*dy
        
        if dr2 == 0:
            # 線段退化為點
            return (x1*x1 + y1*y1) <= radius_m*radius_m

        # 計算圓心到線段的最短距離
        t = -(x1*dx + y1*dy) / dr2
        t = max(0, min(1, t))  # 限制在線段上
        
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy
        
        dist_sq = closest_x*closest_x + closest_y*closest_y
        
        return dist_sq < (radius_m * radius_m)