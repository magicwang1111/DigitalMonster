"""Desktop movement geometry, independent of navigation experiments."""
import math

def advance(position,target,speed=6):
    dx,dy=target[0]-position[0],target[1]-position[1]
    distance=math.hypot(dx,dy)
    if distance<=speed:return tuple(target)
    return (position[0]+dx/distance*speed,position[1]+dy/distance*speed)

def work_areas(root):
    if __import__('os').name=='nt':
        import ctypes
        from ctypes import wintypes
        areas=[]
        class Info(ctypes.Structure):
            _fields_=[('size',wintypes.DWORD),('monitor',wintypes.RECT),('work',wintypes.RECT),('flags',wintypes.DWORD)]
        callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HANDLE,wintypes.HDC,ctypes.POINTER(wintypes.RECT),wintypes.LPARAM)
        def collect(handle,*_):
            info=Info();info.size=ctypes.sizeof(info)
            if ctypes.windll.user32.GetMonitorInfoW(handle,ctypes.byref(info)):
                r=info.work;areas.append((r.left,r.top,r.right,r.bottom))
            return True
        ctypes.windll.user32.GetMonitorInfoW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Info)]
        ctypes.windll.user32.EnumDisplayMonitors.argtypes=[wintypes.HDC,ctypes.POINTER(wintypes.RECT),callback,wintypes.LPARAM]
        ctypes.windll.user32.EnumDisplayMonitors(None,None,callback(collect),0)
        if areas:return areas
    return [(0,0,root.winfo_screenwidth(),root.winfo_screenheight())]
