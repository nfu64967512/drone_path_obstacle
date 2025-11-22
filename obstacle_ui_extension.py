"""
障礙物UI擴展模組 - 修復版
修復顏色格式、改進繞行演算法、圖層管理
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Tuple, List
from obstacle_manager import ObstacleManager, Obstacle
from logger_utils import logger


class ObstacleUIExtension:
    """障礙物UI擴展 - 完整修復版"""
    
    def __init__(self, app):
        self.app = app
        self.obstacle_manager = ObstacleManager()
        
        # 創建狀態
        self.creating_mode = False
        self.delete_mode = False
        self.selected_obstacle: Optional[Obstacle] = None
        
        # 默認參數
        self.default_radius = 5.0
        self.default_safe_distance = 1.0
        
        # 保存原始地圖點擊處理器
        self.original_map_click_handler = None
    
    def add_obstacle_ui(self, parent_frame):
        """添加障礙物管理UI"""
        obstacle_frame = ttk.LabelFrame(parent_frame, text="障礙物管理", 
                                       padding="10", style='Modern.TLabelframe')
        obstacle_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 說明
        info = "🛑 點擊地圖創建障礙物\n   選中後可調整大小"
        ttk.Label(obstacle_frame, text=info, justify=tk.LEFT,
                 font=("Segoe UI", 8), 
                 foreground=self.app.colors['text_secondary']).pack(anchor=tk.W, pady=(0, 5))
        
        # 半徑設定
        ttk.Label(obstacle_frame, text="障礙物半徑:").pack(anchor=tk.W, pady=(5, 0))
        from ui_components import ModernSlider
        self.radius_slider = ModernSlider(
            obstacle_frame, label="半徑", from_=1, to=100,
            value=self.default_radius, resolution=0.5,
            command=self.on_radius_change, unit="m"
        )
        self.radius_slider.pack(fill=tk.X, pady=2)
        self.app.modern_sliders['obstacle_radius'] = self.radius_slider
        
        # 安全距離
        ttk.Label(obstacle_frame, text="安全距離:").pack(anchor=tk.W, pady=(5, 0))
        self.safe_slider = ModernSlider(
            obstacle_frame, label="安全距離", from_=0.5, to=10,
            value=self.default_safe_distance, resolution=0.5,
            command=self.on_safe_distance_change, unit="m"
        )
        self.safe_slider.pack(fill=tk.X, pady=2)
        self.app.modern_sliders['obstacle_safe_dist'] = self.safe_slider
        
        # 按鈕
        button_frame = tk.Frame(obstacle_frame, bg='white')
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.create_btn = ttk.Button(button_frame, text="創建障礙物", 
                                     command=self.toggle_create_mode,
                                     style='Primary.TButton', width=14)
        self.create_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(button_frame, text="刪除障礙物", 
                  command=self.toggle_delete_mode,
                  style='Warning.TButton', width=14).pack(side=tk.LEFT)
        
        # 計數
        self.info_label = ttk.Label(obstacle_frame, text="目前障礙物: 0 個",
                                    font=("Segoe UI", 8),
                                    foreground=self.app.colors['text_secondary'])
        self.info_label.pack(anchor=tk.W, pady=(10, 0))
    
    def toggle_create_mode(self):
        """切換創建模式"""
        if self.creating_mode:
            self.exit_create_mode()
        else:
            self.enter_create_mode()
    
    def enter_create_mode(self):
        """進入創建模式"""
        self.creating_mode = True
        self.delete_mode = False
        self.create_btn.config(text="取消創建")
        
        # 替換地圖點擊處理器
        self.original_map_click_handler = self.app.on_map_click
        self.app.map.add_left_click_map_command(self.on_create_click)
        
        logger.info("進入障礙物創建模式 - 點擊地圖創建")
    
    def exit_create_mode(self):
        """退出創建模式"""
        self.creating_mode = False
        self.create_btn.config(text="創建障礙物")
        
        # 恢復原始處理器
        if self.original_map_click_handler:
            self.app.map.add_left_click_map_command(self.original_map_click_handler)
            self.original_map_click_handler = None
    
    def on_create_click(self, coords):
        """創建障礙物（點擊即創建）"""
        lat, lon = coords
        
        # 創建障礙物對象
        obstacle = self.obstacle_manager.add_obstacle(
            (lat, lon), 
            self.default_radius,
            self.default_safe_distance
        )
        
        # 創建顯示
        self.create_obstacle_display(obstacle)
        
        # 設為選中
        self.selected_obstacle = obstacle
        
        # 更新計數
        self.update_info()
        
        logger.info(f"創建障礙物: 中心({lat:.6f}, {lon:.6f}), "
                   f"半徑{self.default_radius}m")
    
    def create_obstacle_display(self, obstacle: Obstacle):
        """創建障礙物顯示（修復顏色格式）"""
        try:
            lat, lon = obstacle.center
            
            # 標記
            obstacle.marker = self.app.map.set_marker(
                lat, lon,
                text=f"🛑\n{obstacle.radius:.1f}m",
                marker_color_circle="#8B0000",
                marker_color_outside="#8B0000"
            )
            
            # 安全範圍圓圈（使用純色，不帶透明度）
            safe_points = self.generate_circle_points(lat, lon, obstacle.effective_radius, 36)
            obstacle.safe_circle = self.app.map.set_polygon(
                safe_points,
                fill_color="#FFCC99",  # 淺橘色替代半透明
                outline_color="#FF8C00",
                border_width=1
            )
            
            # 障礙物圓圈（使用純色）
            circle_points = self.generate_circle_points(lat, lon, obstacle.radius, 36)
            obstacle.circle = self.app.map.set_polygon(
                circle_points,
                fill_color="#CD5C5C",  # 紅色替代半透明
                outline_color="#8B0000",
                border_width=2
            )
            
            # 加入paths以支持縮放
            self.app.paths.append(obstacle.safe_circle)
            self.app.paths.append(obstacle.circle)
            
        except Exception as e:
            logger.error(f"創建障礙物顯示失敗: {e}")
    
    def on_radius_change(self, value):
        """半徑改變"""
        self.default_radius = value
        
        # 如果有選中的障礙物，更新它
        if self.selected_obstacle:
            self.selected_obstacle.radius = value
            self.update_obstacle_display(self.selected_obstacle)
    
    def on_safe_distance_change(self, value):
        """安全距離改變"""
        self.default_safe_distance = value
        
        if self.selected_obstacle:
            self.selected_obstacle.safe_distance = value
            self.update_obstacle_display(self.selected_obstacle)
    
    def update_obstacle_display(self, obstacle: Obstacle):
        """更新障礙物顯示"""
        try:
            # 刪除舊圓圈
            if obstacle.circle:
                if obstacle.circle in self.app.paths:
                    self.app.paths.remove(obstacle.circle)
                obstacle.circle.delete()
            
            if obstacle.safe_circle:
                if obstacle.safe_circle in self.app.paths:
                    self.app.paths.remove(obstacle.safe_circle)
                obstacle.safe_circle.delete()
            
            # 更新標記文字
            if obstacle.marker:
                obstacle.marker.delete()
            
            lat, lon = obstacle.center
            obstacle.marker = self.app.map.set_marker(
                lat, lon,
                text=f"🛑\n{obstacle.radius:.1f}m",
                marker_color_circle="#8B0000",
                marker_color_outside="#8B0000"
            )
            
            # 重新創建圓圈（使用純色）
            safe_points = self.generate_circle_points(lat, lon, obstacle.effective_radius, 36)
            obstacle.safe_circle = self.app.map.set_polygon(
                safe_points,
                fill_color="#FFCC99",
                outline_color="#FF8C00",
                border_width=1
            )
            
            circle_points = self.generate_circle_points(lat, lon, obstacle.radius, 36)
            obstacle.circle = self.app.map.set_polygon(
                circle_points,
                fill_color="#CD5C5C",
                outline_color="#8B0000",
                border_width=2
            )
            
            # 重新加入paths
            self.app.paths.append(obstacle.safe_circle)
            self.app.paths.append(obstacle.circle)
            
        except Exception as e:
            logger.error(f"更新障礙物顯示失敗: {e}")
    
    def generate_circle_points(self, center_lat, center_lon, radius_m, num_points=36):
        """生成圓形點（正確的公尺轉度數）"""
        import math
        points = []
        
        for i in range(num_points + 1):
            angle = 2 * math.pi * i / num_points
            dlat = (radius_m / 111111.0) * math.cos(angle)
            dlon = (radius_m / 111111.0) * math.sin(angle) / math.cos(math.radians(center_lat))
            points.append((center_lat + dlat, center_lon + dlon))
        
        return points
    
    def toggle_delete_mode(self):
        """切換刪除模式"""
        if self.delete_mode:
            self.exit_delete_mode()
        else:
            self.enter_delete_mode()
    
    def enter_delete_mode(self):
        """進入刪除模式"""
        self.delete_mode = True
        self.creating_mode = False
        
        self.original_map_click_handler = self.app.on_map_click
        self.app.map.add_left_click_map_command(self.on_delete_click)
        
        logger.info("進入刪除模式 - 點擊障礙物刪除")
    
    def exit_delete_mode(self):
        """退出刪除模式"""
        self.delete_mode = False
        
        if self.original_map_click_handler:
            self.app.map.add_left_click_map_command(self.original_map_click_handler)
            self.original_map_click_handler = None
    
    def on_delete_click(self, coords):
        """刪除障礙物"""
        lat, lon = coords
        removed = self.obstacle_manager.remove_nearest_obstacle((lat, lon), threshold_m=100.0)
        
        if removed:
            # 從paths移除
            if removed.circle in self.app.paths:
                self.app.paths.remove(removed.circle)
            if removed.safe_circle in self.app.paths:
                self.app.paths.remove(removed.safe_circle)
            
            # 刪除顯示
            try:
                if removed.marker:
                    removed.marker.delete()
                if removed.circle:
                    removed.circle.delete()
                if removed.safe_circle:
                    removed.safe_circle.delete()
            except:
                pass
            
            if self.selected_obstacle == removed:
                self.selected_obstacle = None
            
            self.update_info()
            logger.info(f"已刪除障礙物: {removed.center}")
        
        # 退出刪除模式
        self.exit_delete_mode()
    
    def clear_all_obstacles(self):
        """清除所有障礙物"""
        for obstacle in self.obstacle_manager.obstacles[:]:
            # 從paths移除
            if obstacle.circle in self.app.paths:
                self.app.paths.remove(obstacle.circle)
            if obstacle.safe_circle in self.app.paths:
                self.app.paths.remove(obstacle.safe_circle)
            
            # 刪除顯示
            try:
                if obstacle.marker:
                    obstacle.marker.delete()
                if obstacle.circle:
                    obstacle.circle.delete()
                if obstacle.safe_circle:
                    obstacle.safe_circle.delete()
            except:
                pass
        
        self.obstacle_manager.clear_all()
        self.selected_obstacle = None
        self.update_info()
        logger.info("已清除所有障礙物")
    
    def update_info(self):
        """更新信息"""
        count = len(self.obstacle_manager.obstacles)
        self.info_label.config(text=f"目前障礙物: {count} 個")
    
    def apply_obstacle_avoidance(self, waypoints, boundary_corners=None):
        """應用障礙物避讓（傳入邊界）"""
        if not self.obstacle_manager.obstacles:
            return waypoints
        
        logger.info(f"應用障礙物繞行: {len(self.obstacle_manager.obstacles)} 個")
        return self.obstacle_manager.filter_waypoints_with_detour(waypoints, boundary_corners)