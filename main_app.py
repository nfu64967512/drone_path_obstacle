"""
主應用程式模組
包含主要的GUI應用程式類
整合障礙物UI擴展模組
"""

import os
import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkintermapview
from typing import List, Tuple, Optional

from config import Config, FlightDynamics, FlightParameters
from logger_utils import logger
from ui_components import ModernStyleManager, ModernSlider
from collision_avoidance import CollisionAvoidanceSystem
from waypoint_generator import OptimizedWaypointGenerator
from region_divider import RegionDivider
from map_manager import MapManager
from obstacle_ui_extension import ObstacleUIExtension


# ==============================
# 主應用程式類
# ==============================
class DronePathPlannerApp(tk.Tk):
    """主應用程式類 - 整合優化航點生成器、間隔功能和障礙物避讓"""
    
    def __init__(self):
        super().__init__()
        self.setup_window()
        self.init_variables()
        self.init_optimized_components()
        self.setup_styles()
        self.create_widgets()
        self.bind_events()
        self._preview_after_id = None
        
        # 延遲初始化地圖
        self.after(100, self.initialize_map)
    
    def setup_window(self):
        """設定視窗"""
        self.title(Config.WINDOW_TITLE)
        self.geometry(Config.WINDOW_SIZE)
        self.minsize(*Config.MIN_WINDOW_SIZE)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_styles(self):
        """設置現代化樣式"""
        self.colors = ModernStyleManager.setup_modern_style(self)
        self.configure(bg=self.colors['bg'])
    
    def init_optimized_components(self):
        """初始化優化組件"""
        # 創建飛行動力學參數
        self.flight_dynamics = FlightDynamics(
            max_acceleration=2.0,
            max_deceleration=2.5,
            max_yaw_acceleration=45.0,
            hover_time=2.0,
            takeoff_time=5.0,
            landing_time=3.0,
            safety_buffer=10.0,
            large_turn_speed_factor=0.7,
            sharp_turn_speed_factor=0.5,
            uturn_speed_factor=0.3
        )
        
        # 初始化優化的航點生成器
        self.waypoint_generator = OptimizedWaypointGenerator()
        
        # 初始化障礙物UI擴展
        self.obstacle_ui_extension = None  # 將在create_widgets後初始化
        
        # 飛行動力學參數變數
        self.dynamics_vars = {
            "最大加速度 [m/s²]": tk.DoubleVar(value=2.0),
            "最大減速度 [m/s²]": tk.DoubleVar(value=2.5),
            "轉向加速度 [deg/s²]": tk.DoubleVar(value=45.0),
            "航點懸停時間 [s]": tk.DoubleVar(value=2.0),
            "安全緩衝時間 [s]": tk.DoubleVar(value=10.0),
            "大角度轉向係數": tk.DoubleVar(value=0.7),
            "銳角轉向係數": tk.DoubleVar(value=0.5),
            "U型轉向係數": tk.DoubleVar(value=0.3),
        }
    
    def init_variables(self):
        """初始化變數"""
        self.corners: List[Tuple[float, float]] = []
        self.markers: List = []
        self.paths: List = []
        self.region_overlays: List = []
        self.start_markers: List = []  # 起點標記
        self.end_markers: List = []    # 終點標記
        
        # 延遲時間管理
        self.loiter_times: List[float] = []  # LOITER等待時間
        self.current_waypoint_results = []  # 當前航點結果
        
        # UI變數
        self.mode_var = tk.StringVar(value="Add")
        self.sub_var = tk.IntVar(value=1)
        self.reduce_overlap_var = tk.BooleanVar(value=True)
        self.show_region_fill_var = tk.BooleanVar(value=False)
        self.region_alpha_var = tk.IntVar(value=20)
        self.path_width_var = tk.IntVar(value=Config.PATH_WIDTH_DEFAULT)
        self.show_waypoints_var = tk.BooleanVar(value=True)
        self.flight_mode_var = tk.StringVar(value="智能避撞")
        
        # 新增：子區域間隔變數
        self.region_spacing_var = tk.DoubleVar(value=3.0)  # 預設3公尺間隔
        
        # 飛行參數變數
        self.param_vars = {
            "高度 [m]": tk.DoubleVar(value=10.0),
            "角度 [deg]": tk.DoubleVar(value=0.0),
            "間距 [m]": tk.DoubleVar(value=5.0),
            "速度 [m/s]": tk.DoubleVar(value=5.0),
            "轉向速度 [deg/s]": tk.DoubleVar(value=60.0),
            "安全間距 [m]": tk.DoubleVar(value=5.0),
        }
        
        # 現代滑桿控件存儲
        self.modern_sliders = {}
    
    def create_widgets(self):
        """建立界面元件"""
        # 主容器
        self.main_container = ttk.Frame(self)
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # 建立地圖
        self.create_map()
        
        # 建立控制面板
        self.create_control_panel()
        
        # 初始化障礙物UI擴展（在地圖創建後）
        self.obstacle_ui_extension = ObstacleUIExtension(self)
    
    def create_map(self):
        """建立地圖元件"""
        # 地圖框架
        map_frame = ttk.Frame(self.main_container)
        map_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 地圖元件
        try:
            self.map = tkintermapview.TkinterMapView(map_frame, corner_radius=0)
            self.map.pack(fill=tk.BOTH, expand=True)
            
            # 地圖管理器
            self.map_manager = MapManager(self.map)
            
        except Exception as e:
            logger.error(f"建立地圖元件失敗: {e}")
            # 建立備用標籤
            backup_label = ttk.Label(map_frame, text="地圖載入失敗\n請檢查網路連線", 
                                   font=("Segoe UI", 14), foreground="red")
            backup_label.pack(expand=True)
    
    def create_control_panel(self):
        """建立控制面板"""
        # 建立可滾動的控制面板
        canvas = tk.Canvas(self.main_container, width=450, bg='white')
        scrollbar = ttk.Scrollbar(self.main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='white')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 綁定滑鼠滾輪事件
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0), pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
        # 在可滾動框架中建立內容
        panel = tk.Frame(scrollable_frame, bg='white', padx=10, pady=10)
        panel.pack(fill=tk.BOTH, expand=True)
        
        # 儲存panel供後續使用
        self.control_panel = panel
        
        # 操作模式框
        self.create_mode_frame(panel)
        
        # 飛行參數框
        self.create_parameters_frame(panel)
        
        # 智能避撞框
        self.create_collision_frame(panel)
        
        # 操作按鈕框
        self.create_operations_frame(panel)
        
        # 地圖選擇框
        self.create_map_selection_frame(panel)
        
        # 使用說明框
        self.create_help_frame(panel)
    
    def create_mode_frame(self, parent):
        """建立操作模式框"""
        mode_frame = ttk.LabelFrame(parent, text="操作模式", padding="10", style='Modern.TLabelframe')
        mode_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 點擊模式
        ttk.Label(mode_frame, text="點擊模式:").pack(anchor=tk.W)
        mode_combo = ttk.Combobox(mode_frame, textvariable=self.mode_var,
                                values=["Add", "Edit"], state="readonly", width=18, style='Modern.TCombobox')
        mode_combo.pack(anchor=tk.W, pady=2)
        
        # 子區分割
        ttk.Label(mode_frame, text="子區分割:").pack(anchor=tk.W, pady=(8, 0))
        sub_combo = ttk.Combobox(mode_frame, textvariable=self.sub_var, 
                    values=[1, 2, 3, 4], state="readonly", width=18, style='Modern.TCombobox')
        sub_combo.pack(anchor=tk.W, pady=2)
        
        # 新增：子區域間隔設定
        ttk.Label(mode_frame, text="子區域間隔:").pack(anchor=tk.W, pady=(8, 0))
        self.modern_sliders['region_spacing'] = ModernSlider(
            mode_frame, label="子區域間隔", from_=0, to=10, 
            value=self.region_spacing_var.get(), resolution=0.5,
            command=self.on_spacing_change, unit="m"
        )
        self.modern_sliders['region_spacing'].pack(fill=tk.X, pady=2)
        
        # 飛行模式選項
        ttk.Label(mode_frame, text="飛行模式:").pack(anchor=tk.W, pady=(8, 0))
        flight_mode_combo = ttk.Combobox(mode_frame, textvariable=self.flight_mode_var,
                                values=["同步飛行", "智能避撞"], state="readonly", width=18, style='Modern.TCombobox')
        flight_mode_combo.pack(anchor=tk.W, pady=2)
        flight_mode_combo.current(1)  # 預設智能避撞
        
        # 選項
        ttk.Checkbutton(mode_frame, text="減少重疊（互補）", 
                       variable=self.reduce_overlap_var).pack(anchor=tk.W, pady=(8, 0))
        ttk.Checkbutton(mode_frame, text="顯示子區域底色", 
                       variable=self.show_region_fill_var).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(mode_frame, text="顯示起終點", 
                       variable=self.show_waypoints_var).pack(anchor=tk.W, pady=2)
        
        # 透明度滑桿（現代化）
        self.modern_sliders['alpha'] = ModernSlider(
            mode_frame, label="底色透明度", from_=0, to=100, 
            value=self.region_alpha_var.get(), resolution=1,
            command=self.on_alpha_change, unit="%"
        )
        self.modern_sliders['alpha'].pack(fill=tk.X, pady=(8, 0))
        
        # 操作按鈕
        button_frame = tk.Frame(mode_frame, bg='white')
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="完成邊界", command=self.finish_boundary, 
                  style='Primary.TButton', width=14).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="刪除最後點", command=self.remove_last_corner, 
                  style='Warning.TButton', width=14).pack(side=tk.LEFT)
    
    def create_parameters_frame(self, parent):
        """建立飛行參數框"""
        param_frame = ttk.LabelFrame(parent, text="飛行參數", padding="10", style='Modern.TLabelframe')
        param_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 使用現代滑桿
        params = [
            ("高度", "高度 [m]", 10.0, 0.1, 1000.0, 0.5, "m"),
            ("角度", "角度 [deg]", 0.0, -180.0, 180.0, 1.0, "°"),
            ("間距", "間距 [m]", 5.0, 0.1, 100.0, 0.5, "m"),
            ("速度", "速度 [m/s]", 5.0, 0.1, 30.0, 0.1, "m/s"),
            ("轉向", "轉向速度 [deg/s]", 60.0, 1.0, 360.0, 1.0, "°/s"),
        ]
        
        for key, label, default, min_val, max_val, increment, unit in params:
            slider = ModernSlider(
                param_frame, label=label.split('[')[0].strip(), 
                from_=min_val, to=max_val, value=default, 
                resolution=increment, command=lambda v, k=label: self.on_param_change(k, v),
                unit=unit
            )
            slider.pack(fill=tk.X, pady=5)
            self.modern_sliders[key] = slider
        
        # 航線寬度
        self.modern_sliders['path_width'] = ModernSlider(
            param_frame, label="航線寬度", from_=1, to=10, 
            value=Config.PATH_WIDTH_DEFAULT, resolution=1,
            command=lambda v: self.schedule_preview_update(), unit="px"
        )
        self.modern_sliders['path_width'].pack(fill=tk.X, pady=5)
    
    def create_collision_frame(self, parent):
        """建立智能避撞設定框"""
        collision_frame = ttk.LabelFrame(parent, text="智能避撞系統", padding="10", style='Modern.TLabelframe')
        collision_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 安全間距設定（固定為5米）
        info_label = ttk.Label(collision_frame, 
                              text="✓ 安全間距: 5公尺\n✓ 自動LOITER等待模式\n✓ 高度錯開RTL返航\n✓ 子區域間隔控制",
                              font=("Segoe UI", 9), foreground=self.colors['success'])
        info_label.pack(anchor=tk.W)
        
        # LOITER時間顯示
        self.loiter_info_label = ttk.Label(collision_frame, 
                                          text="預覽後顯示各區域等待時間",
                                          font=("Segoe UI", 8), foreground=self.colors['text_secondary'])
        self.loiter_info_label.pack(anchor=tk.W, pady=(5, 0))
    
    def create_operations_frame(self, parent):
        """建立操作按鈕框"""
        ops_frame = ttk.LabelFrame(parent, text="操作", padding="10", style='Modern.TLabelframe')
        ops_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 主要操作按鈕
        ttk.Button(ops_frame, text="預覽路徑", command=self.preview_paths, 
                  style='Primary.TButton', width=20).pack(fill=tk.X, pady=3)
        ttk.Button(ops_frame, text="匯出航點", command=self.export_waypoints, 
                  style='Success.TButton', width=20).pack(fill=tk.X, pady=3)
        
        ttk.Separator(ops_frame, orient='horizontal').pack(fill=tk.X, pady=8)
        
        # 清除操作
        ttk.Button(ops_frame, text="清除路徑", command=self.clear_paths, 
                  width=20).pack(fill=tk.X, pady=3)
        ttk.Button(ops_frame, text="清除邊界", command=self.clear_corners, 
                  width=20).pack(fill=tk.X, pady=3)
        ttk.Button(ops_frame, text="重設全部", command=self.reset_all, 
                  style='Warning.TButton', width=20).pack(fill=tk.X, pady=3)
    
    def create_map_selection_frame(self, parent):
        """建立地圖選擇框"""
        map_frame = ttk.LabelFrame(parent, text="地圖設定", padding="10", style='Modern.TLabelframe')
        map_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(map_frame, text="地圖類型:").pack(anchor=tk.W)
        map_var = tk.StringVar()
        map_combo = ttk.Combobox(map_frame, textvariable=map_var, width=18,
                               values=[name for name, _, _ in Config.MAP_SERVERS], 
                               state="readonly", style='Modern.TCombobox')
        map_combo.pack(anchor=tk.W, pady=2)
        map_combo.current(0)
        map_combo.bind('<<ComboboxSelected>>', lambda e: self.switch_map_server(map_combo.current()))
    
    def create_help_frame(self, parent):
        """建立說明框"""
        help_frame = ttk.LabelFrame(parent, text="使用說明", padding="10", style='Modern.TLabelframe')
        help_frame.pack(fill=tk.X)
        
        help_text = (
            "🗺 基本操作:\n"
            "• Add: 新增邊界點 (3-10個)\n"
            "• Edit: 編輯最近的邊界點\n"
            "• 完成邊界後再預覽/匯出\n\n"
            "🚁 智能避撞系統:\n"
            "• 5米安全間距自動避撞\n"
            "• LOITER等待前機離開\n"
            "• 任務結束返回起點\n"
            "• RTL高度自動錯開\n\n"
            "📏 子區域間隔:\n"
            "• 0-10公尺可調間隔\n"
            "• 避免重疊作業區域\n"
            "• 提升飛行安全性\n\n"
            "✨ 專業功能:\n"
            "• 現代化滑桿控制\n"
            "• 完整任務循環\n"
            "• 智能路徑規劃\n"
            "• QGC WPL 110格式匯出"
        )
        
        ttk.Label(help_frame, text=help_text, justify=tk.LEFT,
                 font=("Segoe UI", 9), foreground=self.colors['text_secondary']).pack(anchor=tk.W)
    
    def bind_events(self):
        """綁定事件"""
        self.bind("<Configure>", self.on_resize)
        self.bind("<Return>", self.on_enter_key)
    
    def on_enter_key(self, event=None):
        """處理Enter鍵按下事件以預覽路徑"""
        self.preview_paths()
    
    def on_param_change(self, param_key: str, value: float):
        """參數改變事件"""
        self.param_vars[param_key].set(value)
        self.schedule_preview_update()
    
    def on_alpha_change(self, value):
        """透明度改變事件"""
        self.region_alpha_var.set(int(value))
        if self.region_overlays:
            self.preview_paths()
    
    def on_spacing_change(self, value):
        """新增：間隔改變事件"""
        self.region_spacing_var.set(value)
        self.schedule_preview_update()
    
    def schedule_preview_update(self, delay_ms: int = 120):
        """排程即時預覽"""
        try:
            if self._preview_after_id is not None:
                self.after_cancel(self._preview_after_id)
        except Exception:
            pass
        self._preview_after_id = self.after(delay_ms, self.preview_paths)
    
    def initialize_map(self):
        """初始化地圖"""
        try:
            if hasattr(self, 'map_manager'):
                self.map_manager.initialize_map()
                self.map.add_left_click_map_command(self.on_map_click)
                logger.info("地圖初始化完成")
                
                # 在地圖初始化後，添加障礙物UI到控制面板
                if self.obstacle_ui_extension and hasattr(self, 'control_panel'):
                    # 找到合適的位置插入障礙物UI（在飛行參數和智能避撞之間）
                    self.obstacle_ui_extension.add_obstacle_ui(self.control_panel)
        except Exception as e:
            logger.error(f"地圖初始化失敗: {e}")
    
    def on_resize(self, event):
        """視窗大小改變事件"""
        if event.widget == self:
            try:
                panel_width = 470
                new_width = max(300, event.width - panel_width - 20)
                new_height = max(200, event.height - 20)
                
                if hasattr(self, 'map'):
                    self.map.configure(width=new_width, height=new_height)
            except Exception as e:
                logger.warning(f"調整地圖大小失敗: {e}")
    
    def switch_map_server(self, index):
        """切換地圖伺服器"""
        try:
            if hasattr(self, 'map_manager'):
                self.map_manager.switch_map_server(index)
        except Exception as e:
            logger.error(f"切換地圖伺服器失敗: {e}")
    
    def on_map_click(self, coords):
        """地圖點擊事件"""
        try:
            lat, lon = coords
            mode = self.mode_var.get()
            
            if mode == "Add" and len(self.corners) < Config.MAX_CORNERS:
                self.add_corner_point(lat, lon)
            elif mode == "Edit":
                self.edit_nearest_corner(lat, lon)
                
        except Exception as e:
            logger.error(f"處理地圖點擊失敗: {e}")
            messagebox.showerror("錯誤", f"處理地圖點擊時發生錯誤: {str(e)}")
    
    def add_corner_point(self, lat: float, lon: float):
        """新增角點"""
        try:
            point_num = len(self.corners) + 1
            marker = self.map.set_marker(lat, lon, text=f"P{point_num}")
            
            self.markers.append(marker)
            self.corners.append((lat, lon))
            
            logger.info(f"新增角點 P{point_num}: ({lat:.6f}, {lon:.6f})")
            
        except Exception as e:
            logger.error(f"新增角點失敗: {e}")
    
    def edit_nearest_corner(self, lat: float, lon: float):
        """編輯最近的角點"""
        try:
            if not self.corners:
                return
            
            # 找到最近的角點
            min_dist = float('inf')
            nearest_idx = 0
            
            for i, (c_lat, c_lon) in enumerate(self.corners):
                dist = self.calculate_distance(lat, lon, c_lat, c_lon)
                if dist < min_dist:
                    min_dist = dist
                    nearest_idx = i
            
            # 更新角點位置
            self.markers[nearest_idx].set_position(lat, lon)
            self.corners[nearest_idx] = (lat, lon)
            
            logger.info(f"編輯角點 P{nearest_idx + 1}: ({lat:.6f}, {lon:.6f})")
            
        except Exception as e:
            logger.error(f"編輯角點失敗: {e}")
    
    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """計算兩點間距離"""
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        avg_lat = (lat1 + lat2) / 2
        
        distance = math.sqrt(
            (dlat * Config.EARTH_RADIUS_M) ** 2 + 
            (dlon * Config.EARTH_RADIUS_M * math.cos(math.radians(avg_lat))) ** 2
        )
        return distance
    
    def finish_boundary(self):
        """完成邊界設定"""
        try:
            if len(self.corners) < Config.MIN_CORNERS:
                messagebox.showwarning("錯誤", f"至少需要{Config.MIN_CORNERS}個角點")
                return
            
            # 清除舊的區域顯示
            self.clear_region_overlays()
            
            # 繪製邊界
            boundary_path = self.map.set_path(
                self.corners + [self.corners[0]], 
                color="#FFFFFF", 
                width=2
            )
            self.paths.append(boundary_path)
            
            # 切換到編輯模式
            self.mode_var.set("Edit")
            
            messagebox.showinfo("完成", f"邊界設定完成，共{len(self.corners)}個角點")
            logger.info(f"邊界設定完成，{len(self.corners)}個角點")
            
        except Exception as e:
            logger.error(f"完成邊界設定失敗: {e}")
            messagebox.showerror("錯誤", f"完成邊界設定失敗: {str(e)}")
    
    def remove_last_corner(self):
        """刪除最後一個角點"""
        try:
            if not self.corners:
                return
            
            # 刪除最後的標記和角點
            last_marker = self.markers.pop()
            last_marker.delete()
            self.corners.pop()
            
            logger.info(f"刪除角點，剩餘{len(self.corners)}個邊界點")
            
        except Exception as e:
            logger.error(f"刪除角點失敗: {e}")
    
    def get_flight_parameters(self) -> Optional[FlightParameters]:
        """取得飛行參數"""
        try:
            # 從現代滑桿獲取值
            params = FlightParameters(
                altitude=self.modern_sliders['高度'].get(),
                angle=self.modern_sliders['角度'].get(),
                spacing=self.modern_sliders['間距'].get(),
                speed=self.modern_sliders['速度'].get(),
                yaw_speed=self.modern_sliders['轉向'].get(),
                safety_distance=Config.SAFETY_DISTANCE_M  # 固定5米
            )
            params.validate()
            return params
        except Exception as e:
            messagebox.showerror("參數錯誤", str(e))
            return None
    
    def clear_region_overlays(self):
        """清除區域覆蓋層"""
        try:
            for overlay in self.region_overlays:
                try:
                    overlay.delete()
                except Exception:
                    pass
            self.region_overlays.clear()
        except Exception as e:
            logger.warning(f"清除區域覆蓋層失敗: {e}")
    
    def clear_start_end_markers(self):
        """清除起終點標記"""
        try:
            for marker in self.start_markers + self.end_markers:
                try:
                    marker.delete()
                except Exception:
                    pass
            self.start_markers.clear()
            self.end_markers.clear()
        except Exception as e:
            logger.warning(f"清除起終點標記失敗: {e}")
    
    def preview_paths(self):
        """預覽路徑 - 整合完整的智能避撞功能和障礙物避讓"""
        try:
            # 清除舊的路徑和標記
            self.clear_paths()
            self.clear_region_overlays()
            self.clear_start_end_markers()
            
            if len(self.corners) < Config.MIN_CORNERS:
                messagebox.showwarning("錯誤", f"需要至少{Config.MIN_CORNERS}個角點才能預覽")
                return
            
            # 取得飛行參數
            params = self.get_flight_parameters()
            if not params:
                return
            
            # 分割區域（使用新的間隔功能）
            sub_count = self.sub_var.get()
            spacing_m = self.region_spacing_var.get()  # 取得間隔設定
            
            if len(self.corners) == 4:
                sub_regions = RegionDivider.subdivide_rectangle(self.corners, sub_count, spacing_m)
            else:
                sub_regions = RegionDivider.subdivide_polygon(self.corners, sub_count, spacing_m)
            
            # 繪製子區域
            self.draw_sub_regions(sub_regions)
            
            # 取得飛行模式
            flight_mode = self.flight_mode_var.get()
            
            # 生成航點並計算LOITER時間
            waypoint_results = []
            loiter_times = []
            prev_waypoints = None
            
            for idx, region_corners in enumerate(sub_regions):
                # 確定起始方向
                start_from_left = (idx % 2 == 0) if self.reduce_overlap_var.get() else True
                
                # 計算LOITER時間（智能避撞模式）
                loiter_time = 0.0
                if flight_mode == "智能避撞" and idx > 0 and prev_waypoints:
                    # 計算需要等待前一台離開安全範圍的時間
                    loiter_time = self.waypoint_generator.collision_avoidance.calculate_loiter_delay(
                        prev_waypoints, region_corners[0], params.speed
                    )
                    loiter_time += idx * 5.0  # 額外錯開時間
                
                loiter_times.append(loiter_time)
                
                # 生成完整任務航點
                waypoint_lines, waypoints = self.waypoint_generator.generate_complete_mission(
                    region_corners, params, idx, sub_count, start_from_left, loiter_time
                )
                
                # 應用障礙物避讓（如果有障礙物UI擴展）
                if self.obstacle_ui_extension and waypoints:
                    waypoints = self.obstacle_ui_extension.apply_obstacle_avoidance(waypoints, region_corners)
                
                waypoint_results.append((waypoint_lines, waypoints, loiter_time))
                prev_waypoints = waypoints
                
                # 繪製路徑
                if waypoints:
                    self.draw_flight_paths(waypoints, idx)
                    
                    # 繪製起終點標記
                    if self.show_waypoints_var.get():
                        self.draw_start_end_markers_with_time(waypoints, idx, loiter_time)
            
            # 更新LOITER時間顯示
            self.loiter_times = loiter_times
            self.update_loiter_display()
            
            # 儲存結果供匯出使用
            self.current_waypoint_results = waypoint_results
            
            logger.info(f"預覽完成，共{len(sub_regions)}個子區域，飛行模式：{flight_mode}，間隔：{spacing_m}公尺")
            
        except Exception as e:
            logger.error(f"預覽路徑失敗: {e}")
            messagebox.showerror("預覽錯誤", f"預覽失敗: {str(e)}")
    
    def update_loiter_display(self):
        """更新LOITER時間顯示"""
        if not self.loiter_times:
            return
        
        spacing_m = self.region_spacing_var.get()
        display_text = f"各區域等待時間 (間隔:{spacing_m}m):\n"
        for idx, loiter_time in enumerate(self.loiter_times):
            display_text += f"區域 {idx+1}: {loiter_time:.1f}秒\n"
        
        self.loiter_info_label.config(text=display_text)
    
    def draw_start_end_markers_with_time(self, waypoints: List[Tuple[float, float]], 
                                        region_idx: int, loiter_time: float):
        """繪製起終點標記（包含時間資訊）"""
        try:
            if not waypoints:
                return
            
            # 起點標記（綠色，顯示LOITER時間）
            start_lat, start_lon = waypoints[0]
            start_text = f"S{region_idx+1}"
            if loiter_time > 0:
                start_text += f"\nWait:{loiter_time:.0f}s"
            
            start_marker = self.map.set_marker(
                start_lat, start_lon,
                text=start_text,
                marker_color_circle=Config.START_MARKER_COLOR,
                marker_color_outside=Config.START_MARKER_COLOR
            )
            self.start_markers.append(start_marker)
            
            # 終點標記（紅色）
            end_lat, end_lon = waypoints[-2] if len(waypoints) > 1 else waypoints[-1]
            end_marker = self.map.set_marker(
                end_lat, end_lon,
                text=f"E{region_idx+1}",
                marker_color_circle=Config.END_MARKER_COLOR,
                marker_color_outside=Config.END_MARKER_COLOR
            )
            self.end_markers.append(end_marker)
            
        except Exception as e:
            logger.error(f"繪製起終點標記失敗: {e}")
    
    def draw_sub_regions(self, sub_regions: List[List[Tuple[float, float]]]):
        """繪製子區域"""
        try:
            show_fill = self.show_region_fill_var.get()
            alpha = self.region_alpha_var.get()
            
            for idx, region in enumerate(sub_regions):
                # 繪製邊框
                border = self.map.set_path(
                    region + [region[0]],
                    color=Config.REGION_BORDER_COLOR,
                    width=Config.REGION_BORDER_WIDTH
                )
                self.region_overlays.append(border)
                
                # 繪製填充（如果啟用）
                if show_fill and alpha > 0:
                    try:
                        base_color = Config.REGION_FILL_COLORS[idx % len(Config.REGION_FILL_COLORS)]
                        fill_color = self.blend_with_white(base_color, alpha)
                        
                        polygon = self.map.set_polygon(
                            region,
                            fill_color=fill_color,
                            outline_color=fill_color,
                            border_width=0
                        )
                        self.region_overlays.append(polygon)
                    except Exception as e:
                        logger.warning(f"繪製區域填充失敗: {e}")
                        
        except Exception as e:
            logger.error(f"繪製子區域失敗: {e}")
    
    def blend_with_white(self, hex_color: str, alpha_percent: int) -> str:
        """將顏色與白色混合以模擬透明度"""
        try:
            hex_color = hex_color.lstrip('#')
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            
            alpha = max(0, min(100, alpha_percent)) / 100.0
            
            # 與白色混合
            r2 = int(alpha * r + (1 - alpha) * 255)
            g2 = int(alpha * g + (1 - alpha) * 255)
            b2 = int(alpha * b + (1 - alpha) * 255)
            
            return f"#{r2:02X}{g2:02X}{b2:02X}"
        except Exception:
            return hex_color
    
    def draw_flight_paths(self, waypoints: List[Tuple[float, float]], region_idx: int):
        """繪製飛行路徑"""
        try:
            if len(waypoints) < 2:
                return
            
            color = Config.PATH_COLORS[region_idx % len(Config.PATH_COLORS)]
            path_width = max(1, int(self.modern_sliders['path_width'].get()))
            
            # 繪製連續的路徑段
            for i in range(len(waypoints) - 1):
                path = self.map.set_path(
                    [waypoints[i], waypoints[i + 1]],
                    color=color,
                    width=path_width
                )
                self.paths.append(path)
                
        except Exception as e:
            logger.error(f"繪製飛行路徑失敗: {e}")
    
    def export_waypoints(self):
        """匯出航點 - 整合智能避撞功能"""
        try:
            if len(self.corners) < Config.MIN_CORNERS:
                messagebox.showwarning("錯誤", f"需要至少{Config.MIN_CORNERS}個角點才能匯出")
                return
            
            # 如果沒有預覽結果，先執行預覽
            if not self.current_waypoint_results:
                self.preview_paths()
            
            if not self.current_waypoint_results:
                messagebox.showwarning("錯誤", "無法生成航點")
                return
            
            sub_count = self.sub_var.get()
            flight_mode = self.flight_mode_var.get()
            spacing_m = self.region_spacing_var.get()
            
            if sub_count > 1:
                # 多個檔案匯出
                dir_path = filedialog.askdirectory(title="選擇輸出資料夾")
                if not dir_path:
                    return
                
                exported_files = []
                for idx, (waypoint_lines, _, loiter_time) in enumerate(self.current_waypoint_results, start=1):
                    if not waypoint_lines:
                        continue
                    
                    # 檔案名稱
                    mode_suffix = "_smart" if flight_mode == "智能避撞" else "_sync"
                    spacing_suffix = f"_gap{spacing_m:.1f}m" if spacing_m > 0 else ""
                    file_name = f"drone_{idx}{mode_suffix}{spacing_suffix}.waypoints"
                    file_path = os.path.join(dir_path, file_name)
                    
                    # 寫入檔案
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write("\n".join(waypoint_lines))
                    
                    exported_files.append(file_path)
                
                # 生成飛行計劃說明文件
                info_file = os.path.join(dir_path, "mission_briefing.txt")
                with open(info_file, 'w', encoding='utf-8') as f:
                    f.write("=" * 50 + "\n")
                    f.write("無人機群飛行任務簡報\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(f"飛行模式: {flight_mode}\n")
                    f.write(f"子區域數量: {sub_count}\n")
                    f.write(f"安全間距: {Config.SAFETY_DISTANCE_M}公尺\n")
                    f.write(f"子區域間隔: {spacing_m}公尺\n\n")
                    
                    params = self.get_flight_parameters()
                    f.write("飛行參數:\n")
                    f.write(f"  - 飛行高度: {params.altitude:.1f}公尺\n")
                    f.write(f"  - 飛行速度: {params.speed:.1f}公尺/秒\n")
                    f.write(f"  - 航線間距: {params.spacing:.1f}公尺\n")
                    f.write(f"  - 掃描角度: {params.angle:.1f}度\n\n")
                    
                    if self.obstacle_ui_extension and len(self.obstacle_ui_extension.obstacle_manager.obstacles) > 0:
                        f.write(f"障礙物數量: {len(self.obstacle_ui_extension.obstacle_manager.obstacles)} 個\n\n")
                    
                    f.write("各區域執行計劃:\n")
                    for idx, (_, _, loiter_time) in enumerate(self.current_waypoint_results, start=1):
                        f.write(f"\n區域 {idx}:\n")
                        f.write(f"  - LOITER等待: {loiter_time:.1f}秒\n")
                        rtl_alt = params.altitude + (sub_count - idx) * Config.RTL_ALTITUDE_INCREMENT
                        f.write(f"  - RTL高度: {rtl_alt:.1f}公尺\n")
                        f.write(f"  - 任務特點: 完整循環返回起點\n")
                    
                    f.write("\n" + "=" * 50 + "\n")
                    f.write("任務執行注意事項:\n")
                    f.write("1. 確保所有無人機電池充足\n")
                    f.write("2. 檢查GPS信號強度\n")
                    f.write("3. 確認安全區域無障礙物\n")
                    f.write("4. 監控LOITER等待狀態\n")
                    f.write("5. RTL時注意高度分層\n")
                    f.write(f"6. 子區域間隔設定: {spacing_m}公尺\n")
                
                messagebox.showinfo("匯出成功", 
                    f"已匯出{len(exported_files)}個任務檔案至:\n{dir_path}\n\n"
                    f"飛行模式: {flight_mode}\n"
                    f"子區域間隔: {spacing_m}公尺\n"
                    f"包含任務簡報文件")
                
            else:
                # 單個檔案匯出
                spacing_suffix = f"_gap{spacing_m:.1f}m" if spacing_m > 0 else ""
                default_name = f"drone_mission{spacing_suffix}.waypoints"
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".waypoints",
                    initialfile=default_name,
                    filetypes=[("Waypoint 檔案", "*.waypoints"), ("所有檔案", "*.*")],
                    title="儲存航點檔案"
                )
                if not file_path:
                    return
                
                waypoint_lines = self.current_waypoint_results[0][0]
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("\n".join(waypoint_lines))
                
                messagebox.showinfo("匯出成功", f"已儲存至:\n{file_path}")
            
            logger.info(f"航點匯出完成，飛行模式：{flight_mode}，間隔：{spacing_m}公尺")
            
        except Exception as e:
            logger.error(f"匯出航點失敗: {e}")
            messagebox.showerror("匯出錯誤", f"匯出失敗: {str(e)}")
    
    def clear_paths(self):
        """清除路徑"""
        try:
            for path in self.paths:
                try:
                    path.delete()
                except Exception:
                    pass
            self.paths.clear()
            logger.info("路徑已清除")
        except Exception as e:
            logger.warning(f"清除路徑失敗: {e}")
    
    def clear_corners(self):
        """清除角點"""
        try:
            # 清除標記
            for marker in self.markers:
                try:
                    marker.delete()
                except Exception:
                    pass
            self.markers.clear()
            self.corners.clear()
            
            # 清除其他顯示元素
            self.clear_region_overlays()
            self.clear_start_end_markers()
            self.clear_paths()
            
            # 重設模式
            self.mode_var.set("Add")
            self.current_waypoint_results.clear()
            self.loiter_times.clear()
            
            # 清除LOITER顯示
            self.loiter_info_label.config(text="預覽後顯示各區域等待時間")
            
            logger.info("角點已清除")
            
        except Exception as e:
            logger.error(f"清除角點失敗: {e}")
    
    def reset_all(self):
        """重設所有設定"""
        try:
            if not messagebox.askyesno("確認重設", "確定要重設所有設定嗎？"):
                return
            
            # 清除所有顯示元素
            self.clear_corners()
            
            # 重設參數滑桿
            self.modern_sliders['高度'].set(10.0)
            self.modern_sliders['角度'].set(0.0)
            self.modern_sliders['間距'].set(5.0)
            self.modern_sliders['速度'].set(5.0)
            self.modern_sliders['轉向'].set(60.0)
            self.modern_sliders['path_width'].set(Config.PATH_WIDTH_DEFAULT)
            self.modern_sliders['alpha'].set(20)
            self.modern_sliders['region_spacing'].set(3.0)  # 重設間隔為3公尺
            
            # 重設UI變數
            self.sub_var.set(1)
            self.reduce_overlap_var.set(True)
            self.show_region_fill_var.set(False)
            self.show_waypoints_var.set(True)
            self.mode_var.set("Add")
            self.flight_mode_var.set("智能避撞")
            self.region_spacing_var.set(3.0)
            
            # 清除障礙物
            if self.obstacle_ui_extension:
                self.obstacle_ui_extension.clear_all_obstacles()
            
            logger.info("所有設定已重設")
            messagebox.showinfo("重設完成", "所有設定已重設為預設值")
            
        except Exception as e:
            logger.error(f"重設失敗: {e}")
            messagebox.showerror("重設錯誤", f"重設失敗: {str(e)}")
    
    def on_closing(self):
        """程式關閉事件"""
        try:
            logger.info("程式正在關閉...")
            self.quit()
            self.destroy()
        except Exception as e:
            logger.error(f"程式關閉失敗: {e}")
            self.destroy()