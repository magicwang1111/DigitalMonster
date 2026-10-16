import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
lines = ['# 2026-10-16 GPU 初步训练结果', '',
         '四组模拟器最短路监督实验各有约 30 分钟墙钟预算。每组独立生成 8192 张训练地图，另有验证地图选择检查点，最终评估 512 张未参与训练的 21×21 地图。', '',
         '| 配置 | 实际更新步数 | 批量 | 最终成功率 | 检查点 SHA256 |',
         '|---|---:|---:|---:|---|']
for folder in sorted((root/'data/training').glob('*')):
    report = folder/'report.json'
    if not report.exists():
        continue
    r = json.loads(report.read_text(encoding='utf-8'))
    actual = hashlib.sha256((folder/'best.pt').read_bytes()).hexdigest()
    assert actual == r['checkpoint_sha256'], folder
    lines.append(f"| w{r['width']} r{r['rounds']} seed{r['seed']} | {r['step']} | {r['batch']} | {r['success_rate']:.2%} | {actual} |")
lines += ['', '贪心静态策略成功率 50.20%，随机静态策略成功率 0.20%。训练期间测得双卡 GPU 利用率均为 100%，显存占用分别约 23.3 GB 和 25.6 GB。原始报告峰值包括批量探测，不能全部解释为稳定训练占用。', '',
          '四组均按墙钟预算结束，实际步数未达到上限 30000；已完成最终测试。检查点已下载并校验哈希。在线个体仍运行既有 5×5 策略，大地图模型尚未接入在线行动；这些结果仅证明特定导航任务的学习，不证明通用智能或意识。']
(root/'docs/training-results-2026-10-16.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('\n'.join(lines))
