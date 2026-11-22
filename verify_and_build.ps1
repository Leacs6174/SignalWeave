$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "找不到 $python，请先创建 .venv 并安装 requirements-build.txt"
}

$env:QT_QPA_PLATFORM = "offscreen"
& $python -m unittest discover -s tests -p "test_*.py" -v
if ($LASTEXITCODE -ne 0) {
    throw "测试失败，退出码 $LASTEXITCODE"
}

Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
& $python (Join-Path $PSScriptRoot "build_exe.py")
if ($LASTEXITCODE -ne 0) {
    throw "EXE 构建失败，退出码 $LASTEXITCODE"
}

$exe = Join-Path $PSScriptRoot "dist\SignalWeave\SignalWeave.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    throw "构建结束但未找到 $exe"
}

& (Join-Path $PSScriptRoot "sign_exe.ps1") -Executable $exe
if ($LASTEXITCODE -ne 0) {
    throw "EXE 签名失败，退出码 $LASTEXITCODE"
}

Write-Host ""
Write-Host "验证与构建完成：" -ForegroundColor Green
Write-Host $exe
