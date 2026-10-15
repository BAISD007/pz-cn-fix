# 把生成好的中文字体打包成 zip，用于上传到 GitHub Releases。
# 仓库里不放 110 MB 的二进制，用户也可以自己跑 build_cn_fonts.py 生成。
#
#   powershell -ExecutionPolicy Bypass -File tools\make_release.ps1
#   powershell -ExecutionPolicy Bypass -File tools\make_release.ps1 -Game "D:\...\ProjectZomboid"
param(
    [string]$Game = "",
    [string]$Out = ""
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
if (-not $Out) { $Out = Join-Path $root "dist" }

# 游戏目录：优先 -Game，其次读 python 工具写下的缓存
if (-not $Game) {
    $cfg = Join-Path $env:USERPROFILE "Zomboid\pz-cn-fix\game.txt"
    if (Test-Path $cfg) { $Game = (Get-Content $cfg -Raw).Trim() }
}
if (-not $Game -or -not (Test-Path (Join-Path $Game "ProjectZomboid64.exe"))) {
    throw "找不到游戏目录。先运行一次 python tools\build_cn_fonts.py（会自动记录路径），或用 -Game 'D:\...\ProjectZomboid' 指定"
}

New-Item -ItemType Directory -Force -Path $Out | Out-Null
$stage = Join-Path $Out "stage\media\fonts"
Remove-Item (Join-Path $Out "stage") -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $stage | Out-Null

$fonts = Join-Path $Game "media\fonts"
# 顶层共享档（注意：.fnt 和图集 _NN.png 都要，所以通配符不能带点）
Get-ChildItem $fonts -File | Where-Object { $_.Name -like "zomboid*Chinese*" } |
    ForEach-Object { Copy-Item $_.FullName (Join-Path $stage $_.Name) -Force }
# CN 的 4 个缩放档
foreach ($s in @("1x", "2x", "3x", "4x")) {
    $src = Join-Path $fonts "CN\$s"
    if (-not (Test-Path $src)) { continue }
    $dst = Join-Path $stage "CN\$s"
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    Get-ChildItem $src -File | Where-Object { $_.Name -like "zomboid*Chinese*" } |
        ForEach-Object { Copy-Item $_.FullName (Join-Path $dst $_.Name) -Force }
}

$readme = @"
pz-cn-fix - rebuilt Chinese bitmap fonts (Project Zomboid Build 42)

安装：把 media 文件夹直接解压覆盖到你的游戏根目录（与 ProjectZomboid64.exe 同级），
或者解压到 Zomboid\mods\PZChineseFontPatch\ 下并在游戏里启用模组。

Install: extract the media folder over your Project Zomboid install directory
(same level as ProjectZomboid64.exe), or into Zomboid\mods\PZChineseFontPatch\.

原始字体已由生成脚本备份在 %USERPROFILE%\Zomboid\pz-cn-fix\backup\fonts，
还原：python build_cn_fonts.py --restore

本包含由 Noto Sans SC 生成的位图字体（SIL OFL 1.1），不含任何游戏原始文件。
Not affiliated with The Indie Stone.
"@
Set-Content -Path (Join-Path $Out "stage\README.txt") -Value $readme -Encoding UTF8

$zip = Join-Path $Out "pz-cn-fix-fonts.zip"
Remove-Item $zip -Force -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $Out "stage\*") -DestinationPath $zip
$mb = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host "打包完成: $zip ($mb MB)" -ForegroundColor Green
Write-Host "上传到 GitHub: Releases -> Draft a new release -> 把这个 zip 作为附件" -ForegroundColor Cyan
