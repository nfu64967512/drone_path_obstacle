"""
區域分割器模組
負責將區域分割成子區域，支持間隔設定
"""

import math
from typing import List, Tuple


# ==============================
# 區域分割器（新增間隔功能）
# ==============================
class RegionDivider:
    """區域分割器 - 負責將區域分割成子區域，支持間隔設定"""
    
    @staticmethod
    def bilinear_interpolation(corners: List[Tuple[float, float]], u: float, v: float) -> Tuple[float, float]:
        """雙線性插值（四邊形專用）"""
        if len(corners) != 4:
            raise ValueError("雙線性插值需要4個角點")
        
        p0, p1, p2, p3 = corners  # 左下、右下、右上、左上
        
        x = ((1-u)*(1-v)*p0[0] + u*(1-v)*p1[0] + u*v*p2[0] + (1-u)*v*p3[0])
        y = ((1-u)*(1-v)*p0[1] + u*(1-v)*p1[1] + u*v*p2[1] + (1-u)*v*p3[1])
        
        return (x, y)
    
    @staticmethod
    def subdivide_rectangle(corners: List[Tuple[float, float]], n: int, spacing_m: float = 0.0) -> List[List[Tuple[float, float]]]:
        """分割四邊形區域，支持間隔設定"""
        if len(corners) != 4:
            raise ValueError("矩形分割需要4個角點")
        
        if n == 1:
            return [corners]
        
        regions = []
        
        # 如果有間隔，計算間隔比例
        spacing_ratio = 0.0
        if spacing_m > 0:
            # 計算區域的平均寬度來決定間隔比例
            width1 = RegionDivider._calculate_distance(corners[0], corners[1])
            width2 = RegionDivider._calculate_distance(corners[3], corners[2])
            avg_width = (width1 + width2) / 2
            spacing_ratio = min(0.1, spacing_m / avg_width)  # 限制最大間隔比例為10%
        
        if n in (2, 3):
            # 水平分割
            for i in range(n):
                # 計算分割位置，考慮間隔
                if n > 1:
                    total_spacing = spacing_ratio * (n - 1)
                    effective_width = 1.0 - total_spacing
                    segment_width = effective_width / n
                    
                    u0 = i * (segment_width + spacing_ratio)
                    u1 = u0 + segment_width
                else:
                    u0 = 0
                    u1 = 1
                
                # 確保邊界值在有效範圍內
                u0 = max(0, min(1, u0))
                u1 = max(0, min(1, u1))
                
                if u0 >= u1:
                    continue
                
                bl = RegionDivider.bilinear_interpolation(corners, u0, 0)
                br = RegionDivider.bilinear_interpolation(corners, u1, 0)
                tr = RegionDivider.bilinear_interpolation(corners, u1, 1)
                tl = RegionDivider.bilinear_interpolation(corners, u0, 1)
                
                regions.append([bl, br, tr, tl])
        
        elif n == 4:
            # 2x2網格分割
            grid_spacing = spacing_ratio / 2  # 2x2網格的間隔調整
            for j in range(2):
                for i in range(2):
                    # 計算每個格子的位置，考慮間隔
                    u0 = i * (0.5 + grid_spacing) - grid_spacing/2 if i > 0 else 0
                    u1 = u0 + 0.5 - grid_spacing
                    v0 = j * (0.5 + grid_spacing) - grid_spacing/2 if j > 0 else 0
                    v1 = v0 + 0.5 - grid_spacing
                    
                    # 確保邊界值在有效範圍內
                    u0 = max(0, min(1, u0))
                    u1 = max(0, min(1, u1))
                    v0 = max(0, min(1, v0))
                    v1 = max(0, min(1, v1))
                    
                    if u0 >= u1 or v0 >= v1:
                        continue
                    
                    bl = RegionDivider.bilinear_interpolation(corners, u0, v0)
                    br = RegionDivider.bilinear_interpolation(corners, u1, v0)
                    tr = RegionDivider.bilinear_interpolation(corners, u1, v1)
                    tl = RegionDivider.bilinear_interpolation(corners, u0, v1)
                    
                    regions.append([bl, br, tr, tl])
        
        return regions
    
    @staticmethod
    def subdivide_polygon(corners: List[Tuple[float, float]], n: int, spacing_m: float = 0.0) -> List[List[Tuple[float, float]]]:
        """分割任意多邊形（使用水平條帶），支持間隔設定"""
        if n == 1:
            return [corners]
        
        # 取得邊界
        min_y = min(p[1] for p in corners)
        max_y = max(p[1] for p in corners)
        total_height = max_y - min_y
        
        # 計算間隔
        if spacing_m > 0:
            # 將間隔從公尺轉換為緯度（約111111公尺/度）
            spacing_deg = spacing_m / 111111.0
            total_spacing = spacing_deg * (n - 1)
            
            # 如果間隔太大，調整到合理範圍
            if total_spacing >= total_height * 0.5:
                spacing_deg = total_height * 0.1 / (n - 1)  # 限制總間隔不超過10%
                total_spacing = spacing_deg * (n - 1)
        else:
            spacing_deg = 0
            total_spacing = 0
        
        # 有效高度
        effective_height = total_height - total_spacing
        strip_height = effective_height / n
        
        regions = []
        
        for i in range(n):
            # 計算條帶邊界，考慮間隔
            y_start = min_y + i * (strip_height + spacing_deg)
            y_end = y_start + strip_height
            
            # 確保不超出邊界
            y_start = max(min_y, y_start)
            y_end = min(max_y, y_end)
            
            if y_start >= y_end:
                continue
            
            # 找到條帶的邊界點
            strip_points = []
            
            # 加入與條帶邊界相交的點
            for j in range(len(corners)):
                x1, y1 = corners[j]
                x2, y2 = corners[(j + 1) % len(corners)]
                
                # 檢查與y_start的交點
                if (y1 <= y_start <= y2) or (y2 <= y_start <= y1):
                    if abs(y2 - y1) > 1e-10:
                        x_intersect = x1 + (y_start - y1) * (x2 - x1) / (y2 - y1)
                        strip_points.append((x_intersect, y_start))
                
                # 檢查與y_end的交點
                if (y1 <= y_end <= y2) or (y2 <= y_end <= y1):
                    if abs(y2 - y1) > 1e-10:
                        x_intersect = x1 + (y_end - y1) * (x2 - x1) / (y2 - y1)
                        strip_points.append((x_intersect, y_end))
                
                # 加入在條帶內的原始頂點
                if y_start <= y1 <= y_end:
                    strip_points.append((x1, y1))
            
            # 去重並排序
            if len(strip_points) >= 3:
                # 按角度排序形成多邊形
                cx = sum(p[0] for p in strip_points) / len(strip_points)
                cy = sum(p[1] for p in strip_points) / len(strip_points)
                
                strip_points.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
                regions.append(strip_points)
            else:
                regions.append(corners)  # 備用方案
        
        return regions if regions else [corners]
    
    @staticmethod
    def _calculate_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """計算兩點間距離（簡化版，用於估算）"""
        dlat = p2[0] - p1[0]
        dlon = p2[1] - p1[1]
        return math.sqrt(dlat**2 + dlon**2) * 111111.0  # 轉換為公尺