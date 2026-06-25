# OKX Price Floating Window

Windows 桌面 OKX 行情悬浮窗，支持现货、永续、交割和期权搜索添加，最多显示 4 个标的。

## 功能

- WebSocket 实时 ticker 推送，REST 自动兜底
- 价格、24h 涨跌百分比展示
- 右键设置颜色、透明度、显示标的
- 双击悬浮窗退出，左键拖动位置
- PyInstaller 一键打包

## 使用

```powershell
python -m pip install -r requirements.txt
python main.py
```

## 打包

```powershell
python build.py
```

产物输出到 `dist/OKX_Price.exe`。
