"""
智能避撞系統模組
基於5米安全間距的智能避撞系統
"""

import math
from typing import List, Tuple


# ==============================
# 智能避撞系統
# ==============================
class CollisionAvoidanceSystem:
    """智能避撞系統 - 基於5米安全間距"""
    
    def __init__(self, safety_distance: float = 5.0):
        self.safety_distance = safety_distance
        self.earth_radius_m = 111111.0
    
    def calculate_loiter_delay(self, prev_waypoints: List[Tuple[float, float]], 
                              current_start: Tuple[float, float],
                              cruise_speed: float) -> float:
        """
        計算需要的loiter等待時間
        當前一台無人機離開安全範圍後，下一台才能開始任務
        """
        if not prev_waypoints or len(prev_waypoints) < 2:
            return 0.0
        
        # 找到前一台無人機離開安全範圍的時間點
        clearance_time = 0.0
        cumulative_distance = 0.0
        
        for i in range(len(prev_waypoints) - 1):
            segment_distance = self.calculate_distance(
                prev_waypoints[i][0], prev_waypoints[i][1],
                prev_waypoints[i+1][0], prev_waypoints[i+1][1]
            )
            cumulative_distance += segment_distance
            
            # 檢查是否已經離開起點的安全範圍
            distance_from_start = self.calculate_distance(
                current_start[0], current_start[1],
                prev_waypoints[i+1][0], prev_waypoints[i+1][1]
            )
            
            if distance_from_start > self.safety_distance:
                # 計算到達這個點的時間
                clearance_time = cumulative_distance / cruise_speed
                break
        
        # 加上額外的安全緩衝
        return clearance_time + 2.0  # 2秒額外緩衝
    
    def calculate_distance(self, lat1: float, lon1: float, 
                         lat2: float, lon2: float) -> float:
        """計算兩點間的精確距離（公尺）"""
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        avg_lat = (lat1 + lat2) / 2
        
        distance = math.sqrt(
            (dlat * self.earth_radius_m) ** 2 + 
            (dlon * self.earth_radius_m * math.cos(math.radians(avg_lat))) ** 2
        )
        return distance
    
    def insert_loiter_command(self, waypoint_lines: List[str], 
                            loiter_time: float, insert_after_line: int = 2) -> List[str]:
        """
        在航點文件中插入LOITER命令
        MAV_CMD_NAV_LOITER_TIME (19) - 在當前位置懸停指定時間
        """
        if loiter_time <= 0:
            return waypoint_lines
        
        new_lines = []
        seq_offset = 0
        
        for i, line in enumerate(waypoint_lines):
            # 跳過註釋行
            if line.startswith('#'):
                new_lines.append(line)
                continue
            
            new_lines.append(line)
            
            # 在速度設定後加入LOITER命令
            if i == insert_after_line and not line.startswith('#'):
                seq_offset += 1
                # MAV_CMD_NAV_LOITER_TIME: 在當前位置懸停
                loiter_line = f"{seq_offset}\t0\t3\t19\t{loiter_time:.1f}\t0\t0\t0\t0\t0\t0\t1"
                new_lines.append(loiter_line)
        
        # 更新所有後續序列號
        return self.update_sequence_numbers(new_lines, seq_offset)
    
    def update_sequence_numbers(self, lines: List[str], offset: int) -> List[str]:
        """更新序列號"""
        if offset == 0:
            return lines
        
        final_lines = []
        for i, line in enumerate(lines):
            if line.startswith('#') or i <= 3:  # 註釋和前幾行不變
                final_lines.append(line)
            else:
                parts = line.split('\t')
                if len(parts) > 0 and parts[0].isdigit():
                    seq = int(parts[0])
                    if seq > 2:  # 只更新後續航點
                        parts[0] = str(seq + offset)
                    final_lines.append('\t'.join(parts))
                else:
                    final_lines.append(line)
        
        return final_lines