"""Windows desktop companion. Uses the same remote identity; stores no second organism."""
import json
import math
import random
import os
from pathlib import Path
import queue
import socket
import subprocess
import threading
import time
import tkinter as tk
from tkinter import messagebox
import urllib.request
import webbrowser

from PIL import Image, ImageTk

ROOT = Path(__file__).resolve().parents[1]
CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
BASE = 'http://127.0.0.1:8765'


class Companion:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('基尔兽')
        self.root.geometry('330x410+1100+450')
        self.root.configure(bg='#111827')
        self.root.attributes('-topmost', True)
        self.root.resizable(False, False)
        self.root.overrideredirect(True)
        if os.name == 'nt':
            self.root.wm_attributes('-transparentcolor','#111827')
        self.token = ''
        self.tunnel = None
        self.messages = queue.Queue()
        self.closed = threading.Event()
        self.stage = -1
        self.form_override = None
        self.animation = 'idle'
        self.animation_until = 0
        self.last_interaction=time.monotonic()
        self.next_wander=time.monotonic()+15
        self.pinned=False
        self.saved_position=None
        self.move_target=None
        try:
            settings=json.loads((ROOT/'data/desktop-settings.json').read_text(encoding='utf-8'))
            self.pinned=bool(settings.get('pinned',False))
            self.saved_position=settings.get('position')
        except (OSError,ValueError):pass
        self.wander_direction=-1
        self.frame_number = 0
        self.connected = False
        self.popup = None
        self.name = tk.StringVar(value='基尔兽')
        self.bubble = tk.StringVar(value='正在连接她的记忆与世界……')
        self.heading=tk.Label(self.root, textvariable=self.name, bg='#111827', fg='#e5e7eb',
                 font=('Microsoft YaHei UI', 11, 'bold'))
        self.canvas = tk.Canvas(self.root, width=310, height=260, bg='#111827', highlightthickness=0)
        self.canvas.pack()
        self.sprite = self.canvas.create_image(155, 135)
        self.canvas.bind('<Button-1>', lambda _: self.action('/api/interact', {'action': 'pet'}))
        self.canvas.bind('<Double-Button-1>', lambda _: self.action('/api/explore',{}))
        self.canvas.bind('<Button-3>', self.context_menu)
        self.status_label=tk.Label(self.root, textvariable=self.bubble, bg='#111827', fg='#9ee5ce',
                 wraplength=300, font=('Microsoft YaHei UI', 10), height=3)
        buttons = self.toolbar = tk.Frame(self.root, bg='#202b3e')
        for text, command in [('摸摸', lambda:self.action('/api/interact', {'action':'pet'})),
                              ('喂食', lambda:self.action('/api/interact', {'action':'feed'})),
                              ('探索', lambda:self.action('/api/explore',{})), ('进化', self.growth_window)]:
            tk.Button(buttons, text=text, command=command, bg='#26354b', fg='white',
                      relief='flat', padx=10).pack(side='left', padx=3)
        self.root.bind('<Enter>',lambda _:self.show_tools())
        self.root.bind('<Leave>',lambda _:self.root.after(350,self.hide_tools))
        self.canvas.bind('<ButtonPress-1>',self.begin_drag)
        self.canvas.bind('<B1-Motion>',self.drag)
        self.canvas.bind('<ButtonRelease-1>',self.end_drag)
        self.load_sprite(0)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.bind('<Escape>', lambda _:self.close())
        self.animate()
        self.pump()
        threading.Thread(target=self.connect_loop, daemon=True).start()
        if self.saved_position and len(self.saved_position)==2:
            self.root.after(150,lambda:self.place_window(*self.saved_position))

    def place_window(self,x,y):
        if os.name=='nt':
            import ctypes
            from ctypes import wintypes
            api=ctypes.windll.user32
            api.GetParent.argtypes=[wintypes.HWND];api.GetParent.restype=wintypes.HWND
            api.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
            hwnd=api.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            api.SetWindowPos(hwnd,0,int(x),int(y),0,0,0x0015)
        else:
            self.root.geometry(f'{self.root.winfo_width()}x{self.root.winfo_height()}{int(x):+d}{int(y):+d}')

    def show_tools(self):
        self.last_interaction=time.monotonic()
        if self.animation=='walk':self.animation='idle';self.animation_until=0
        self.toolbar.pack(pady=5)

    def hide_tools(self):
        widget=self.root.winfo_containing(self.root.winfo_pointerx(),self.root.winfo_pointery())
        if widget is not None and widget.winfo_toplevel()==self.root:return
        self.toolbar.pack_forget();self.status_label.pack_forget()

    def begin_drag(self,event):
        self.drag_origin=(event.x_root,event.y_root,self.root.winfo_x(),self.root.winfo_y())
        self.dragged=False

    def drag(self,event):
        x,y,wx,wy=self.drag_origin
        if abs(event.x_root-x)+abs(event.y_root-y)>5:self.dragged=True
        if self.dragged:self.place_window(wx+event.x_root-x,wy+event.y_root-y)

    def end_drag(self,event):
        if not self.dragged:self.action('/api/interact',{'action':'pet'})
        self.move_target=None

    def toggle_pin(self):
        self.pinned=not self.pinned
        self.move_target=None;self.animation='idle';self.animation_until=0
        (ROOT/'data').mkdir(exist_ok=True)
        (ROOT/'data/desktop-settings.json').write_text(json.dumps({'pinned':self.pinned,
            'position':[self.root.winfo_x(),self.root.winfo_y()]}),encoding='utf-8')

    def api(self, path, body=None):
        req = urllib.request.Request(BASE+path,
            json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
            {'Authorization':'Bearer '+self.token, 'Content-Type':'application/json'})
        # Loopback never uses system HTTP proxies.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=8) as response:
            return json.load(response)

    def verify_tunnel(self):
        # Verify port ownership before handing a bearer token to any local HTTP listener.
        command = "$c=Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue; if($c){Get-CimInstance Win32_Process -Filter ('ProcessId='+$c[0].OwningProcess)|Select-Object Name,CommandLine|ConvertTo-Json -Compress}"
        proc = subprocess.run(['powershell', '-NoProfile', '-Command', command], capture_output=True,
                              text=True, timeout=15, creationflags=CREATE_NO_WINDOW)
        if not proc.stdout.strip():
            self.tunnel = subprocess.Popen(['ssh', '-N', '-o', 'BatchMode=yes', '-o', 'ExitOnForwardFailure=yes',
                '-o','ServerAliveInterval=30','-L','127.0.0.1:8765:127.0.0.1:8765','seetacloud-5090x2'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
            self.closed.wait(2)
            if self.tunnel.poll() is not None:
                raise RuntimeError('SSH 隧道未能启动')
            return self.verify_tunnel()
        owner = json.loads(proc.stdout)
        cmd = owner.get('CommandLine') or ''
        if owner.get('Name', '').lower() != 'ssh.exe' or '127.0.0.1:8765:127.0.0.1:8765' not in cmd or 'seetacloud-5090x2' not in cmd:
            raise RuntimeError('8765 端口被其他程序占用，未向它发送访问令牌')

    def connect_loop(self):
        while not self.closed.is_set():
            try:
                if not self.connected:
                    self.verify_tunnel()
                    path = ROOT/'data'/'remote.token'
                    path.parent.mkdir(exist_ok=True)
                    if not path.exists():
                        proc = subprocess.run(['ssh','-o','BatchMode=yes','seetacloud-5090x2',
                            'cat /root/autodl-tmp/DigitalMonster/data/access.token'],
                            capture_output=True, text=True, timeout=15, creationflags=CREATE_NO_WINDOW)
                        if proc.returncode or not proc.stdout.strip():
                            raise RuntimeError('无法读取连接令牌')
                        path.write_text(proc.stdout.strip(), encoding='utf-8')
                    self.token = path.read_text(encoding='utf-8').strip()
                pet = self.api('/api/pet')
                snapshot=self.api('/api/model')
                local=ROOT/'data/companion-model.json'
                temp=local.with_suffix('.tmp')
                temp.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
                os.replace(temp,local)
                self.connected = True
                self.messages.put(('state', pet))
            except Exception as exc:
                self.connected = False
                self.messages.put(('notice', '暂未连接：'+str(exc)[:90]))
            self.closed.wait(5)

    def load_sprite(self, stage):
        if stage == self.stage:
            return
        sheet = Image.open(ROOT/'digitalmon'/'static'/'pet'/'evolution-pixel.png').convert('RGBA')
        w, h = sheet.size
        x, y = min(stage,3) % 2, min(stage,3) // 2
        sprite = sheet.crop((x*w//2, y*h//2, (x+1)*w//2, (y+1)*h//2))
        sprite.thumbnail((245,245), Image.Resampling.NEAREST)
        self.photo = ImageTk.PhotoImage(sprite)
        self.canvas.itemconfig(self.sprite, image=self.photo)
        self.stage = stage
        self.frames = {}
        for action in ('idle', 'pet', 'feed', 'evolve', 'bread', 'walk'):
            path = ROOT/'digitalmon'/'static'/'pet'/f'{["guilmon","growlmon","wargrowlmon","gallantmon","gallantmon-cm","gallantmon-x"][stage]}-{action}.gif'
            if path.exists():
                from PIL import ImageSequence
                with Image.open(path) as gif:
                    self.frames[action] = [ImageTk.PhotoImage(f.convert('RGBA')) for f in ImageSequence.Iterator(gif)]
                    if action=='walk':
                        from PIL import ImageOps
                        gif.seek(0)
                        self.frames['walk_right']=[ImageTk.PhotoImage(ImageOps.mirror(f.convert('RGBA'))) for f in ImageSequence.Iterator(gif)]
        if stage >= 4 and not self.frames.get('idle') and self.frames.get('feed'):
            self.frames['idle'] = [self.frames['feed'][-1]]

    def animate(self):
        if self.closed.is_set():
            return
        if time.monotonic() > self.animation_until:
            self.animation = 'idle'
        now=time.monotonic()
        state=getattr(self,'pet',{})
        if (self.animation=='idle' and now>=self.next_wander and now-self.last_interaction>5
            and not self.pinned and not state.get('paused') and not state.get('stopped')
            and self.form_override is None
            and self.frames.get('walk')):
            from .motion import work_areas
            areas=[a for a in work_areas(self.root) if a[2]-a[0]>=330 and a[3]-a[1]>=410]
            if areas:
                left,top,right,bottom=random.choice(areas)
                self.move_target=(random.randint(left,right-330),random.randint(top,bottom-410))
                self.animation='walk';self.animation_until=now+20;self.next_wander=now+24
        if self.animation=='walk':
            if self.pinned or not self.move_target or state.get('paused') or state.get('stopped'):
                self.animation='idle'
            else:
                from .motion import advance
                position=(self.root.winfo_x(),self.root.winfo_y())
                x,y=advance(position,self.move_target)
                self.wander_direction=1 if x>position[0] else -1
                self.place_window(round(x),round(y))
                if abs(x-self.move_target[0])+abs(y-self.move_target[1])<2:
                    self.animation='idle';self.move_target=None;self.next_wander=now+random.uniform(2,8)
        frames = self.frames.get('walk_right' if self.animation=='walk' and self.wander_direction>0 else self.animation, [])
        if frames:
            self.canvas.itemconfig(self.sprite, image=frames[self.frame_number % len(frames)])
            self.frame_number += 1
        self.root.after(300 if self.animation=='transition' else 400 if self.animation == 'bread' else 180 if self.animation == 'feed' else 100, self.animate)

    def pump(self):
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == 'state':
                    self.pet = value
                    previous_stage = self.stage
                    self.load_sprite(self.form_override if self.form_override is not None else value['stage'])
                    if self.form_override is None and 0 <= previous_stage < value['stage'] < 4:
                        names=['guilmon','growlmon','wargrowlmon','gallantmon']
                        transition=ROOT/'digitalmon/static/pet'/f'{names[previous_stage]}-to-{names[value["stage"]]}.gif'
                        if transition.exists():
                            from PIL import ImageSequence
                            with Image.open(transition) as gif:
                                self.frames['transition']=[ImageTk.PhotoImage(f.convert('RGBA')) for f in ImageSequence.Iterator(gif)]
                        self.animation = 'transition' if transition.exists() else 'evolve'
                        self.animation_until = time.monotonic()+2.4
                        self.frame_number = 0
                    self.name.set((value['form'] if self.form_override is None else
                        ['基尔兽','古拉兽','大古拉兽','红莲骑士兽','红莲骑士兽 CM','红莲骑士兽 X'][self.form_override]+'（预览）'))
                    if not getattr(self, 'notice_until', 0) > time.monotonic():
                        self.bubble.set('行为：'+{'observe':'观察','ask_food':'想吃面包','seek_touch':'想被摸摸','rest':'休息'}.get(value.get('brain',{}).get('action'),'观察')+' · 学习更新 '+str(value.get('brain',{}).get('updates',0))+' 次\n陪伴记录 '+str(value['interactions'])+' 次')
                elif kind == 'animation':
                    self.animation = value
                    self.animation_until = time.monotonic() + (1.6 if value == 'bread' else 2.16)
                    self.frame_number = 0
                else:
                    self.bubble.set(value)
                    self.notice_until = time.monotonic()+8
                    if self.popup and self.popup.winfo_exists():
                        self.history.insert('end', '基尔兽（系统回执）：'+value+'\n\n')
                        self.history.see('end')
        except queue.Empty:
            pass
        if not self.closed.is_set():
            self.root.after(150, self.pump)

    def action(self, path, body):
        self.last_interaction=time.monotonic()
        if path == '/api/interact':
            self.animation = 'feed' if body.get('action') == 'feed' else 'pet'
            self.animation_until = time.monotonic()+2.4
        def work():
            try:
                if not self.connected:
                    raise RuntimeError('仍在连接服务器')
                result = self.api(path, body)
                if path == '/api/interact' and body.get('action') == 'feed':
                    self.messages.put(('animation', 'bread' if self.stage == 0 and result.get('snack') == 'guilmon_bread' else 'feed'))
                self.messages.put(('notice', result.get('reply','操作已记录')))
            except Exception as exc:
                self.messages.put(('notice','操作未完成：'+str(exc)[:100]))
        threading.Thread(target=work, daemon=True).start()

    def interaction_window(self):
        if self.popup and self.popup.winfo_exists():
            self.popup.lift()
            return
        self.popup = tk.Toplevel(self.root)
        self.popup.title('与基尔兽互动')
        self.popup.geometry('480x420')
        self.history = tk.Text(self.popup, wrap='word', font=('Microsoft YaHei UI',11), bg='#111827', fg='#e5e7eb')
        self.history.pack(fill='both', expand=True)
        self.history.insert('end','你可以摸摸、喂食、保存想告诉她的话。\n当前没有自由对话模型；回复是明确标注的系统回执。\n\n')
        line = tk.Entry(self.popup, font=('Microsoft YaHei UI',12))
        line.pack(fill='x', padx=8, pady=8)
        def send(*_):
            value = line.get().strip()
            if value:
                self.history.insert('end','你：'+value+'\n')
                line.delete(0,'end')
                self.action('/api/message', {'text':value})
        line.bind('<Return>',send)
        tk.Button(self.popup,text='发送并保存记忆',command=send).pack(pady=(0,8))

    def growth_window(self):
        pet = getattr(self,'pet',None)
        if not pet:
            return messagebox.showinfo('成长记录','仍在连接服务器。',parent=self.root)
        progress=pet.get('progress',{})
        now=f"当前：喂食{progress.get('feeds',0)}，摸摸{progress.get('touches',0)}，学习更新{progress.get('learning_updates',0)}，活动{progress.get('active_steps',0)}步，探索来源{progress.get('unique_sources',0)}个"
        messagebox.showinfo('进化条件与进度',now+'\n\n'+'\n\n'.join(pet['requirements'])+'\n\n这些是养成进化规则，不是通用智能能力认证。',parent=self.root)

    def context_menu(self, event):
        menu = tk.Menu(self.root,tearoff=0)
        menu.add_command(label='解除固定，自由活动' if self.pinned else '固定在当前位置',command=self.toggle_pin)
        preview = tk.Menu(menu, tearoff=0)
        for index, form in enumerate(['基尔兽','古拉兽','大古拉兽','红莲骑士兽','红莲骑士兽 CM','红莲骑士兽 X 抗体']):
            def show(i=index):
                self.form_override=i
                self.load_sprite(i)
                self.animation='feed'
                self.animation_until=time.monotonic()+2.16
                self.frame_number=0
                self.bubble.set('形象预览：不改变实际成长阶段')
            preview.add_command(label=form, command=show)
        preview.add_command(label='恢复真实成长形态',command=lambda:setattr(self,'form_override',None))
        menu.add_cascade(label='像素动作图鉴（预览）',menu=preview)
        menu.add_command(label='打开观察台',command=lambda:webbrowser.open(BASE+'/#'+self.token))
        menu.add_command(label='暂停活动和实验',command=lambda:self.action('/api/control',{'action':'pause'}))
        menu.add_command(label='继续活动',command=lambda:self.action('/api/control',{'action':'resume'}))
        menu.add_command(label='停止活动和实验',command=lambda:self.action('/api/control',{'action':'stop'}))
        menu.add_separator()
        menu.add_command(label='关闭桌面窗口（服务器继续运行）',command=self.close)
        menu.tk_popup(event.x_root,event.y_root)

    def close(self):
        self.closed.set()
        # Closing the visual companion is not a request to stop the remote organism.
        self.root.destroy()


def main():
    app = Companion()
    app.root.mainloop()


if __name__ == '__main__':
    main()
