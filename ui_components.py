"""
UI組件模組
包含現代化樣式管理器和自定義UI組件
"""

import tkinter as tk
from tkinter import ttk


# ==============================
# 現代化樣式管理器
# ==============================
class ModernStyleManager:
    """現代化UI樣式管理器"""
    
    @staticmethod
    def setup_modern_style(root):
        """設置現代化主題樣式"""
        style = ttk.Style(root)
        
        # 選擇主題
        style.theme_use('clam')
        
        # 定義顏色方案
        colors = {
            'primary': '#2196F3',
            'primary_dark': '#1976D2',
            'secondary': '#4CAF50',
            'accent': '#FF5722',
            'bg': '#F5F5F5',
            'card': '#FFFFFF',
            'text': '#212121',
            'text_secondary': '#757575',
            'border': '#E0E0E0',
            'hover': '#E3F2FD',
            'success': '#4CAF50',
            'warning': '#FF9800',
            'error': '#F44336'
        }
        
        # 配置LabelFrame樣式
        style.configure('Modern.TLabelframe', 
                       background=colors['card'],
                       bordercolor=colors['border'],
                       relief='flat',
                       borderwidth=1)
        style.configure('Modern.TLabelframe.Label',
                       background=colors['card'],
                       foreground=colors['primary_dark'],
                       font=('Segoe UI', 10, 'bold'))
        
        # 配置按鈕樣式
        style.configure('Primary.TButton',
                       background=colors['primary'],
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none',
                       font=('Segoe UI', 9))
        style.map('Primary.TButton',
                 background=[('active', colors['primary_dark']),
                           ('pressed', colors['primary_dark'])])
        
        style.configure('Success.TButton',
                       background=colors['success'],
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none',
                       font=('Segoe UI', 9))
        style.map('Success.TButton',
                 background=[('active', '#388E3C'),
                           ('pressed', '#388E3C')])
        
        style.configure('Warning.TButton',
                       background=colors['warning'],
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none',
                       font=('Segoe UI', 9))
        
        # 配置Scale樣式 (更現代的滑桿)
        style.configure('Modern.Horizontal.TScale',
                       background=colors['card'],
                       troughcolor=colors['border'],
                       borderwidth=0,
                       lightcolor=colors['primary'],
                       darkcolor=colors['primary_dark'])
        
        # 配置Combobox樣式
        style.configure('Modern.TCombobox',
                       fieldbackground=colors['card'],
                       bordercolor=colors['border'],
                       arrowcolor=colors['primary'])
        
        return colors


# ==============================
# 自定義現代滑桿組件
# ==============================
class ModernSlider(tk.Frame):
    """現代化滑桿組件"""
    
    def __init__(self, parent, label="", from_=0, to=100, value=50, 
                 resolution=1, command=None, unit="", **kwargs):
        super().__init__(parent, bg='white', **kwargs)
        
        self.command = command
        self.unit = unit
        
        # 標籤和值顯示
        top_frame = tk.Frame(self, bg='white')
        top_frame.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(top_frame, text=label, font=('Segoe UI', 9), 
                bg='white', fg='#424242').pack(side=tk.LEFT)
        
        self.value_label = tk.Label(top_frame, text=f"{value}{unit}", 
                                   font=('Segoe UI', 9, 'bold'),
                                   bg='white', fg='#2196F3')
        self.value_label.pack(side=tk.RIGHT)
        
        # 滑桿容器
        slider_frame = tk.Frame(self, bg='white', height=30)
        slider_frame.pack(fill=tk.X)
        slider_frame.pack_propagate(False)
        
        # 創建Canvas作為滑桿軌道
        self.canvas = tk.Canvas(slider_frame, height=6, bg='white', 
                               highlightthickness=0)
        self.canvas.pack(fill=tk.X, pady=12)
        
        # 繪製軌道
        self.track = self.canvas.create_rectangle(0, 0, 0, 6, 
                                                 fill='#E0E0E0', outline='')
        self.fill = self.canvas.create_rectangle(0, 0, 0, 6, 
                                                fill='#2196F3', outline='')
        
        # 滑塊
        self.thumb = self.canvas.create_oval(0, -4, 14, 10, 
                                            fill='#1976D2', outline='white', width=2)
        
        # 變數和參數
        self.min_val = from_
        self.max_val = to
        self.resolution = resolution
        self.current_value = value
        
        # 綁定事件
        self.canvas.bind('<Button-1>', self.on_click)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<Configure>', self.on_resize)
        
        # 初始化位置
        self.after(10, self.update_position)
    
    def on_resize(self, event):
        """調整大小時更新軌道"""
        width = event.width
        self.canvas.coords(self.track, 0, 0, width, 6)
        self.update_position()
    
    def on_click(self, event):
        """點擊設置值"""
        self.set_value_from_x(event.x)
    
    def on_drag(self, event):
        """拖動設置值"""
        self.set_value_from_x(event.x)
    
    def set_value_from_x(self, x):
        """根據x座標設置值"""
        width = self.canvas.winfo_width()
        if width <= 1:
            return
        
        # 計算值
        ratio = max(0, min(1, x / width))
        value = self.min_val + ratio * (self.max_val - self.min_val)
        
        # 應用分辨率
        value = round(value / self.resolution) * self.resolution
        value = max(self.min_val, min(self.max_val, value))
        
        if value != self.current_value:
            self.current_value = value
            self.update_position()
            if self.command:
                self.command(value)
    
    def update_position(self):
        """更新滑塊位置"""
        width = self.canvas.winfo_width()
        if width <= 1:
            return
        
        # 計算位置
        ratio = (self.current_value - self.min_val) / (self.max_val - self.min_val)
        x = ratio * width
        
        # 更新填充和滑塊
        self.canvas.coords(self.fill, 0, 0, x, 6)
        self.canvas.coords(self.thumb, x-7, -4, x+7, 10)
        
        # 更新值標籤
        if self.resolution == int(self.resolution):
            self.value_label.config(text=f"{int(self.current_value)}{self.unit}")
        else:
            self.value_label.config(text=f"{self.current_value:.1f}{self.unit}")
    
    def get(self):
        """獲取當前值"""
        return self.current_value
    
    def set(self, value):
        """設置值"""
        self.current_value = max(self.min_val, min(self.max_val, value))
        self.update_position()