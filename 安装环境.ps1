# Lumen one-click setup (Windows) / Lumen 一键装环境（Windows）
# Right-click this file > "Run with PowerShell", or in a terminal / 右键“用 PowerShell 运行”，或在终端运行：
#   powershell -ExecutionPolicy Bypass -File .\安装环境.ps1
# Needs Python 3.12 (python.org, default location); Node.js 18+ only to rebuild the interface.
# 需要先装好 Python 3.12（python.org 默认位置即可）；Node.js 18 以上只在重新打包界面时需要。
# Steps / 做的事:
#   1. .venv with Lumen itself (requirements-dev.txt) / 在本文件夹建 .venv，装上 Lumen 本体
#   2. Libraries for the tools in tools\ (CodeCut, CodePage ...), into the same .venv, and pypdf for CodePDF / 配套工具要的库（也装进这个 .venv），CodePDF 的 pypdf
#   3. Rebuild the interface when Node.js is installed (a built one is included) / 装了 Node 时重新打包界面（已附带打包好的）
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

function Say($en, $zh, $colour = 'Gray') { Write-Host "$en / $zh" -ForegroundColor $colour }

# A program run here that fails stops setup, saying which step (PowerShell does not stop by itself when one exits with an error)
function Stop-IfFailed($en, $zh) {
    if ($LASTEXITCODE -ne 0) {
        Say "Failed: $en (exit code $LASTEXITCODE). Fix what is shown above, then run this again." "失败：$zh（退出码 $LASTEXITCODE）。按上面显示的原因解决后，再运行一次本脚本。" 'Red'
        exit 1
    }
}

function Find-Python312 {
    $local = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
    if (Test-Path $local) { return $local }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { $p = & py -3.12 -c "import sys;print(sys.executable)" 2>$null; if ($LASTEXITCODE -eq 0 -and $p) { return $p.Trim() } }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { $v = & python -c "import sys;print('%d.%d' % sys.version_info[:2])"; if ($v -eq '3.12') { return $python.Source } }
    return $null
}

$py = Find-Python312
if (-not $py) { Say 'Python 3.12 was not found. Install it from python.org, then run this again.' '没有找到 Python 3.12。请先从 python.org 安装，再运行本脚本。' 'Red'; exit 1 }
Write-Host "Python: $py"

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    Say '1/3 Creating .venv ...' '1/3 建 .venv ……'
    & $py -m venv .venv
    Stop-IfFailed 'creating .venv' '建 .venv'
}
Say '1/3 Installing Lumen ...' '1/3 装 Lumen 本体 ……'
& .venv\Scripts\python.exe -m pip install --upgrade pip
& .venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Stop-IfFailed 'installing Lumen' '装 Lumen 本体'

Say '2/3 Installing what the tools need ...' '2/3 装配套工具需要的库 ……'
# into Lumen's own .venv too: the tools run with it (codedoctor/video.py python()), and the user's Python is left alone
& .venv\Scripts\python.exe -m pip install -r tools\codecut\requirements.txt
Stop-IfFailed 'installing what the tools need' '装配套工具需要的库'
& .venv\Scripts\python.exe -m pip install --target tools\codepdf\libs -r tools\codepdf\requirements.txt
Stop-IfFailed 'installing what CodePDF needs' '装 CodePDF 需要的库'

$npm = Get-Command npm -ErrorAction SilentlyContinue
if ($npm) {
    Say '3/3 Rebuilding the interface ...' '3/3 重新打包界面 ……'
    Push-Location web
    & npm install
    & npm run build
    if ($LASTEXITCODE -ne 0) { Say 'The interface could not be rebuilt: the one already built is used.' '界面没能重新打包：用已经打包好的那份。' 'Yellow' }
    Pop-Location
} else {
    Say '3/3 No Node.js: using the interface already built.' '3/3 没有装 Node.js：用已经打包好的界面。'
}

Write-Host ''
Say 'Checking the other programs ...' '检查其他程序 ……'
$checks = @(
    @{ cmd = 'claude'; en = 'Claude Code: npm i -g @anthropic-ai/claude-code, then run claude once to sign in'; zh = 'Claude Code：npm i -g @anthropic-ai/claude-code，再运行一次 claude 登录' },
    @{ cmd = 'codex'; en = 'Codex: npm i -g @openai/codex, then run codex once to sign in'; zh = 'Codex：npm i -g @openai/codex，再运行一次 codex 登录' },
    @{ cmd = 'node'; en = 'Node.js 18+ (nodejs.org): needed to install Claude Code or Codex'; zh = 'Node.js 18 以上（nodejs.org）：装 Claude Code 或 Codex 要用' },
    @{ cmd = 'blender'; en = 'Blender (blender.org): only for Code3D and CodeCAD'; zh = 'Blender（blender.org）：只有 Code3D 和 CodeCAD 要用' }
)
$aiFound = $false
foreach ($c in $checks) {
    if (Get-Command $c.cmd -ErrorAction SilentlyContinue) {
        Say "  ok: $($c.cmd)" "  已装：$($c.cmd)" 'Green'
        if ($c.cmd -in 'claude', 'codex') { $aiFound = $true }
    } else {
        Say "  missing: $($c.en)" "  没装：$($c.zh)" 'Yellow'
    }
}
if (-not $aiFound) { Say 'No Claude Code or Codex: you can also enter an API key in Lumen the first time it opens.' '没有 Claude Code 或 Codex：也可以第一次打开 Lumen 时填一个 API key。' 'Yellow' }

Write-Host ''
Say 'Done. Start Lumen with:' '装好了。启动 Lumen：' 'Green'
Write-Host '  .venv\Scripts\codedoctor-desktop.exe'
