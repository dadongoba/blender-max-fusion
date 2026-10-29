# Blender Max Fusion · Blender / Max / Maya 工作流

[English](README.en.md) · GPL-3.0-or-later · Blender **5.2.x** · 集成预览版

在同一 Blender 中切换 Blender、Max 与 Maya 风格的界面和操作。仓库包含插件源码、简体中文翻译、全部内嵌依赖，以及 AI 可执行的安装 skill。无需另外安装 BsMax、Blender Max 或 Maya Workflow Kit。

## 让 AI 安装

先安装 Git 和 Blender 5.2.x，然后拉取：

```bash
git clone https://github.com/dadongoba/blender-max-fusion.git
cd blender-max-fusion
```

在这个目录打开支持文件和命令行操作的 AI 编程助手，发送：

> 请阅读 AGENTS.md 和 skills/install-blender-max-fusion/SKILL.md，为我的 Blender 安装这个插件并启用简体中文。先检查 Blender 版本和运行状态，安装后验证启用结果。

支持 skill 安装的助手也可以把 `skills/install-blender-max-fusion` 安装为个人 skill。仅复制 skill 时仍需要拉取完整仓库；插件资源不包含在单独的 skill 文件夹内。

## 命令行安装

需要 Python **3.11+**，也可以使用 Blender 自带的 `python.exe`。以下以 Windows PowerShell 为例，路径替换为自己的 Blender 安装位置：

```powershell
python scripts/install.py --blender "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --dry-run
python scripts/install.py --blender "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --language zh
```

正常安装会复制源码到 Blender 用户扩展目录，备份旧版，然后通过 CLI 启动 Blender 并启用插件。`--language zh` 同时将 Blender 全局界面语言设为简体中文；省略它则保持原语言。`--language en` 选择英文。首次启用默认保持 Blender 模式，使用顶栏 Blender / Max / Maya 按钮切换。

**如果 Blender 正在运行，先保存并正常关闭它。** 不方便关闭时先执行 `--no-launch`，只安装文件；当前会话仍运行旧代码，稍后关闭 Blender 再激活：

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --python "$PWD\scripts\enable_in_blender.py" -- --language zh
```

安装器输出验证文件 `fusion-install-result.json` 的完整位置。只有其中 `"ok": true` 才表示启用成功。启用不能使用 `--background`，因为部分内嵌工具初始化时需要 GPU。脚本不控制鼠标、键盘或桌面 UI，也不修改当前项目文件。

## 手动安装 ZIP

```bash
python scripts/build.py
```

在 Blender 的 Preferences → Get Extensions 菜单中选择 **Install from Disk**，选择 `dist/blender_max_fusion-0.3.1.zip` 并启用。保持原有语言或在 Preferences → Interface 中选择简体中文并启用界面翻译。

## 更新与回退

关闭 Blender 后运行 `git pull --ff-only`，再执行安装命令。旧插件保存在安装器输出的 `fusion-backups` 目录；不会覆盖 `startup.blend`、用户项目或其它扩展文件。回退时关闭 Blender，将当前 `blender_max_fusion` 目录移到备份位置，再将所需备份目录复制回原扩展位置并重新启动。

启用时会通过迁移逻辑停用可能冲突的旧插件 ID，包括 `blender_max`、`blender_studio_max`、`BsMax_for_BlenderMax`、`BsMax` 和 `allset`。文件不会被删除。仅复制文件不保存设置；激活步骤会保存 Blender 用户偏好。

## 翻译、兼容性与验证范围

- 默认英文与简体中文词库位于 `addon/blender_max_fusion/zh_CN.json`。内置 Blender 标签同时使用 Blender 自带翻译；尚未覆盖的插件字符串保留英文，不宣称全量翻译。
- Windows + Blender 5.2 是当前主要验证环境。安装脚本也识别 Linux PATH 和 macOS Applications 路径，但这两个系统尚未完成交互式验收。其它 Blender 版本暂不支持。
- 包含原工作区恢复、Max ↔ Maya 直接交接、延迟回调保护，以及 Maya 面板注册和快捷键数据缓存优化。已验证后台逻辑和模块生命周期；实际视觉跳动需要交互式复测。
- Max 模式对全新且未改动的默认场景应用空场景、0–100 帧和 30fps 等默认值；不要把模式切换理解为只修改配色。

验证入口：

```bash
python -m unittest discover -s tests
python scripts/build.py
```

交互检查：在 Blender “建模”页依次执行 Max → Maya → Blender，以及 Maya → Max → Blender，两次均应返回原来的“建模”页。首次工作区载入仍可能产生短暂布局变化。

## 许可证与来源

本集成采用 [GPL-3.0-or-later](LICENSE)，不是 Autodesk 官方产品。第三方来源和许可证见 [THIRD_PARTY.md](addon/blender_max_fusion/THIRD_PARTY.md) 与 [licenses](addon/blender_max_fusion/licenses)。保留了 Blender Max、BsMax、Maya Workflow Kit 和中文翻译库的原始声明。
