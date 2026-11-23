# SignalWeave

本地运行的 CD 光谱与 CHI 电化学数据合并工具。将原始 TXT 整理为面向
Origin 的宽表，所有数据均在本地处理。

![SignalWeave 界面](ui-preview.png)

## 主要功能

- **CD 光谱**：读取 JASCO `XYDATA` TXT，合并 `CD`、`HT`、`Abs` 通道；
  可生成 G 因子数值列，或复制可粘贴到 Origin 公式行的 G 因子公式。
- **电化学**：读取 CHI TXT，自动识别电位、时间、频率等横坐标；首列固定为
  横坐标，后续列按文件和文件内数据列顺序排列。
- **精确并集**：只合并文件中实际存在的横坐标，不插值、不补造测量点；
  缺失值保持空白。不同横坐标的数据不能合并到同一张表。
- **便捷输出**：支持复制、取消勾选下载导出文件，以及直接用于 Origin 的
  表头格式。
- **工程与预览**：工程文件保存源文件路径和勾选状态；支持最近工程、通道配置、
  日间/夜间主题及可缩放的数据折线或散点预览。

便携版请从 [Releases](https://github.com/Leacs6174/SignalWeave/releases/latest)
下载 Windows 11 x64 压缩包，解压后运行 `SignalWeave.exe`。

## 本地构建

环境要求：Windows 11 x64、Python 3.13、PowerShell。

```powershell
Set-Location 'F:\coding\SignalWeave'

# 1. 创建隔离环境并安装构建依赖
& 'F:\coding\python3\python3itself\python.exe' -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-build.txt

# 2. 运行测试
$env:QT_QPA_PLATFORM = 'offscreen'
& '.\.venv\Scripts\python.exe' -B -m unittest discover -s tests -p 'test_*.py' -v
Remove-Item Env:QT_QPA_PLATFORM

# 3. 从源码运行
& '.\.venv\Scripts\pythonw.exe' .\app.py
```

执行完整构建：测试、打包 EXE 并使用本机证书签名。

```powershell
& '.\verify_and_build.ps1'
```

生成可分发的便携 ZIP：

```powershell
& '.\.venv\Scripts\python.exe' .\package_portable.py
```

构建产物：

```text
dist\SignalWeave\SignalWeave.exe
release\SignalWeave Win11 x64.zip
```

默认签名用于验证 EXE 完整性，不会自动获得公共 CA 或 SmartScreen 信任。

## 代码签名政策

Free code signing provided by [SignPath.io](https://about.signpath.io/),
certificate by [SignPath Foundation](https://signpath.org/).

- Committers and reviewers: [Leacs6174](https://github.com/Leacs6174)
- Approvers: [Leacs6174](https://github.com/Leacs6174)

Privacy: This program does not transfer any information to other networked
systems unless specifically requested by the user or the person installing or
operating it.

## 许可证

[GNU Affero General Public License v3.0 or later](LICENSE)
（`AGPL-3.0-or-later`）。
