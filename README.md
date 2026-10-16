# 基尔兽

## 一键启动

双击项目根目录的 **启动基尔兽.bat**。当前机器使用 `D:\miniconda3\pythonw.exe`；换机器时修改 BAT 中的 `DM_PY`。需要 Python、Pillow、Tkinter、Windows OpenSSH，以及配置好的 `seetacloud-5090x2` SSH 连接。运行失败可在终端执行 `python -m digitalmon.desktop` 查看错误。

桌面快捷方式也可启动。网络或服务器不可用时会显示连接错误；不会另建一个新个体冒充原来的基尔兽。

## 一个个体、一份学习状态

每只基尔兽的个体 UUID 同时作为宠物网络 ID，网络权重、驱动状态、最近行动、学习更新次数保存在同一个 SQLite 个体状态中。换外观不换模型，重启恢复同一个模型。界面从服务器读取真实网络行动，而不是用离线实验分数解释宠物行为。

当前网络是小型可检查的感知—动作关联网络。内部驱动输入连接到观察、索食、寻求抚摸、休息等输出；照料事件以明确的监督关联更新权重，并记录更新前后数值及原因。这仍是初级关联学习，不等同于自主发现复杂奖励，也没有实现 Dosidicus 完整的神经发生和突触可塑性机制。

参考项目 [Dosidicus](https://github.com/ViciousSquid/Dosidicus) 的共同学习引擎、可观察网络及经历影响行为的设计方向。本项目没有复制其源码。

## 互动与动画

点击摸摸或喂食。普通食物为金黄色十字纹圆面包，累计喂食会遇到基尔兽造型面包彩蛋。嘴、手臂、尾巴的喂食动作使用独立姿态帧。右键图鉴可预览其他形态；预览不代表已经进化。

## 当前边界

大地图模型属于早期导航实验，不再作为宠物进化依据。宠物自身的进化能力评测尚未建立，自动进化暂不开放。当前模型只学习有限照料关联；尚无自由语言理解、通用智能或意识证明。不能用这份原型声称已经创造生命。

## 数据与服务

远端项目根目录 `/root/autodl-tmp/DigitalMonster`，个体状态位于 `data/life.sqlite`。令牌在 `data/access.token`；本地连接令牌放在已忽略的 `data/remote.token`，不要提交。服务启动：`bash /root/autodl-tmp/DigitalMonster/app/scripts/remote-service.sh start`。

测试：`python -m unittest discover -s tests -v`。
