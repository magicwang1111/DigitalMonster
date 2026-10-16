"""Windows desktop companion. Uses the same remote identity; stores no second organism."""
import json
import math
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
        self.root.title('初生 · 基尔兽')
        self.root.geometry('330x410+1100+450')
        self.root.configure(bg='#111827')
        self.root.attributes('-topmost', True)
        self.root.resizable(False, False)
        self.token = ''
        self.tunnel = None
        self.messages = queue.Queue()
        self.closed = threading.Event()
        self.stage = -1
        self.form_override = None
        self.animation = 'idle'
        self.animation_until = 0
        self.frame_number = 0
        self.connected = False
        self.popup = None
        self.name = tk.StringVar(value='初生 · 基尔兽')
        self.bubble = tk.StringVar(value='正在连接她的记忆与世界……')
        tk.Label(self.root, textvariable=self.name, bg='#111827', fg='#e5e7eb',
                 font=('Microsoft YaHei UI', 14, 'bold')).pack(pady=(10,0))
        self.canvas = tk.Canvas(self.root, width=310, height=260, bg='#111827', highlightthickness=0)
        self.canvas.pack()
        self.sprite = self.canvas.create_image(155, 135)
        self.canvas.bind('<Button-1>', lambda _: self.action('/api/interact', {'action': 'pet'}))
        self.canvas.bind('<Double-Button-1>', lambda _: self.interaction_window())
        self.canvas.bind('<Button-3>', self.context_menu)
        tk.Label(self.root, textvariable=self.bubble, bg='#111827', fg='#9ee5ce',
                 wraplength=300, font=('Microsoft YaHei UI', 10), height=3).pack()
        buttons = tk.Frame(self.root, bg='#111827')
        buttons.pack(pady=5)
        for text, command in [('摸摸', lambda:self.action('/api/interact', {'action':'pet'})),
                              ('喂食', lambda:self.action('/api/interact', {'action':'feed'})),
                              ('互动', self.interaction_window), ('成长', self.growth_window)]:
            tk.Button(buttons, text=text, command=command, bg='#26354b', fg='white',
                      relief='flat', padx=10).pack(side='left', padx=3)
        self.load_sprite(0)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.bind('<Escape>', lambda _:self.root.iconify())
        self.animate()
        self.pump()
        threading.Thread(target=self.connect_loop, daemon=True).start()

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
        for action in ('idle', 'pet', 'feed', 'evolve', 'bread'):
            path = ROOT/'digitalmon'/'static'/'pet'/f'{["guilmon","growlmon","wargrowlmon","gallantmon","gallantmon-cm","gallantmon-x"][stage]}-{action}.gif'
            if path.exists():
                from PIL import ImageSequence
                with Image.open(path) as gif:
                    self.frames[action] = [ImageTk.PhotoImage(f.convert('RGBA')) for f in ImageSequence.Iterator(gif)]
        if stage >= 4 and not self.frames.get('idle') and self.frames.get('feed'):
            self.frames['idle'] = [self.frames['feed'][-1]]

    def animate(self):
        if self.closed.is_set():
            return
        if time.monotonic() > self.animation_until:
            self.animation = 'idle'
        frames = self.frames.get(self.animation, [])
        if frames:
            self.canvas.itemconfig(self.sprite, image=frames[self.frame_number % len(frames)])
            self.frame_number += 1
        self.root.after(400 if self.animation == 'bread' else 180 if self.animation == 'feed' else 100, self.animate)

    def pump(self):
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == 'state':
                    self.pet = value
                    previous_stage = self.stage
                    self.load_sprite(self.form_override if self.form_override is not None else value['stage'])
                    if self.form_override is None and previous_stage >= 0 and previous_stage != value['stage']:
                        self.animation = 'evolve'
                        self.animation_until = time.monotonic()+2.4
                        self.frame_number = 0
                    self.name.set(value['name']+' · '+(value['form'] if self.form_override is None else
                        ['基尔兽','古拉兽','大古拉兽','红莲骑士兽','红莲骑士兽 CM','红莲骑士兽 X'][self.form_override]+'（预览）'))
                    if not getattr(self, 'notice_until', 0) > time.monotonic():
                        self.bubble.set('陪伴记录 '+str(value['interactions'])+' 次 · 亲密度 '+str(value['bond'])+'\n双击我打开互动，右键查看控制菜单')
                elif kind == 'animation':
                    self.animation = value
                    self.animation_until = time.monotonic() + (1.6 if value == 'bread' else 2.16)
                    self.frame_number = 0
                else:
                    self.bubble.set(value)
                    self.notice_until = time.monotonic()+8
                    if self.popup and self.popup.winfo_exists():
                        self.history.insert('end', '初生（系统回执）：'+value+'\n\n')
                        self.history.see('end')
        except queue.Empty:
            pass
        if not self.closed.is_set():
            self.root.after(150, self.pump)

    def action(self, path, body):
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
        self.popup.title('与初生互动')
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
        messagebox.showinfo('成长与进化', '\n\n'.join(pet['requirements'])+'\n\n'+pet['capability_note'],parent=self.root)

    def context_menu(self, event):
        menu = tk.Menu(self.root,tearoff=0)
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
