# 第三方代码与修改记录

## Dosidicus

- 项目：https://github.com/ViciousSquid/Dosidicus
- 来源提交：`dfc8ed3feff5682f37081e57e6f4090e7fb87a6b`
- 复制文件：`src/plasticity.py`、`src/brain_constants.py`，保存于 `digitalmon/vendor/dosidicus/`。
- 保留原文件内容和模块注释；接入代码位于 `digitalmon/brain.py`，每64步将持久化观察窗口交给原始 `PlasticityEngine`，将驱动到动作的更新写回同一模型，并记录原因。
- 本轮未接入上游 STDP 与神经发生模块；不声称已完整移植 Dosidicus。
- 许可证：GPL-2.0，全文保存于根目录 `LICENSE`。项目代码以该许可发布。角色素材不在此代码许可声明范围内，不据此主张拥有数码宝贝角色权利。

## Voyager

- 项目：https://github.com/MineDojo/Voyager
- 来源提交：`55e45a880755d0c8c66ca7fb5fe7962ac8974f89`
- 提取并改编 `voyager/agents/curriculum.py` 的 `clean_up_tasks`，位于 `digitalmon/curriculum.py`。
- 保留任务完成顺序、去重、将已解决任务从失败记录移除。持久化改用本项目 SQLite 事务；下一探索任务选择尚未完成且失败较少的课程。
- 未移植上游 Minecraft、LLM、向量库和 JavaScript 执行模块，也不声称具备 Voyager 的开放式技能生成能力。
- MIT 版权与许可全文保存于 `digitalmon/vendor/VOYAGER-LICENSE`。
