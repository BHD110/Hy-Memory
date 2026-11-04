# Windows SDK / Core 验证记录

日期：2026-11-03。按用户最新要求，仅验证 SDK 与 Core；桌面交互由用户验收。

## 最终结果

真实 API 验收 12 项通过；确定性回归 5 项通过。测试使用独立临时数据目录、合成对话与记忆，以及当前配置的 OpenCode Go hy3 模型和本地 bge-small-zh-v1.5 嵌入。模型能力来自真实探测，没有手动设置成功状态。

- Core 拒绝无效令牌。
- 模型结构化输出、嵌入探测、激活、过期配置版本拒绝。
- ChatGPT 历史包上传、预览、重复上传恢复、确认、导入。
- 已有记忆 TXT 上传、预览、确认、导入。
- 两类输入进入 SDK 并完成处理，两个任务均 completed。
- 对话原文检索命中 1 条；记忆检索命中 2 条。
- 问答正确回答导入记忆中的预算，并带记忆引用。
- 手动新增同一请求重复提交不产生第二条记忆。
- 修改记忆后读取新内容，删除后返回 404。
- 记忆库与图谱 API 正常响应；这仅证明接口可读，不代表复杂图谱内容的全面验收。

回归测试覆盖：确认重试后的 SDK 请求编号持久化、原始幂等编号不变；OpenCode 请求头只发给准确域名；Windows 上传回执重开与确认；拒绝公共 ACL；已有记忆没有用户对话轮次时仍能入队，重复导入只产生一个任务。

## 本轮修复

1. Windows 文件导入不再使用虚假的 POSIX 权限位；新建导入目录使用当前用户 / SYSTEM / Administrators 的 ACL，并校验已有目录和文件。发现不安全的旧目录时拒绝，不擅自放宽权限。
2. Windows 文件刷盘使用可写句柄，避免 Bad file descriptor；目录不调用不支持的 fd fsync，保留文件刷盘与替换。
3. Windows fstat 与 lstat 的 ctime 含义不同；改为同种查询前后比较，保留文件身份、大小、链接数和修改时间检查。
4. memory_content 输入直接创建独立的 SDK add_extracted 任务，避免被对话分轮逻辑丢弃。
5. HY SDK 2.0.8 显式原文搜索纳入 shadow 状态。成功提取后原文进入此状态，之前只搜 active 导致正常导入后搜不到。修补仅针对显式 raw 搜索，普通记忆搜索保持原行为。

## 可重复执行

在仓库根目录运行：

```powershell
apps/core/.venv/Scripts/python.exe scripts/apply_hy_sdk_compat.py
apps/core/.venv/Scripts/python.exe scripts/windows-regression-tests.py
apps/core/.venv/Scripts/python.exe scripts/windows-core-validation.py
```

真实验收读取已激活模型的配置和系统凭据，仅向模型发送合成测试内容；不修改正式数据目录。测试结束关闭独立 Core，保留临时结果以供检查。

SDK 修补脚本检查版本及目标代码结构；版本变化时拒绝套用，需重新验证。Windows 构建脚本在 uv sync 后自动应用它。单独执行 uv sync / 重装 SDK 后需重新运行修补脚本。

## 边界和当前运行状态

Python 语法检查、uv lock 离线一致性检查、git diff --check 通过。

本轮未操作桌面。正在运行的桌面 Core 仍持有启动时加载的旧代码；上述新增文件导入与 SDK 修补需重启桌面后加载。为避免再次打断进行中的记忆任务，本轮没有强制重启。

检查时正式库队列：49 completed、85 pending、1 running、1 unknown、2 assembling。这不是隔离测试结果；正式历史队列尚未全部完成。其中 unknown 是先前停止进程时已进入 SDK 的任务，不能冒充成功或直接修改数据库清零。

未全面覆盖：所有第三方应用各自导出格式、数万条历史的性能、各种断电/崩溃时序、实际桌面交互。不能据此宣称全部功能均已验收。
