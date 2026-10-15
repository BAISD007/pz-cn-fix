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

$py = "python"
$probe = & $py -c "import sys; sys.path.insert(0, r'$here'); from _common import find_game; print(find_game(quiet=True) or '')" 2>$null
if ($Game) { $probe = $Game }
if (-not $probe -or -not (Test-Path (Join-Path $probe "ProjectZomboid64.exe"))) {
    throw "找不到游戏目录，请用 -Game 指定，例如 -Game 'D:\Steam\steamapps\common\ProjectZomboid'"
}

New-Item -ItemType Directory -Force -Path $Out | Out-Null
$stage = Join-Path $Out "stage\media\fonts"
Remove-Item (Join-Path $Out "stage") -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $stage | Out-Null

$fonts = Join-Path $probe "media\fonts"
# 顶层共享档
Get-ChildItem $fonts -File | Where-Object { $_.Name -like "zomboid*Chinese.*" } |
    ForEach-Object { Copy-Item $_.FullName (Join-Path $stage $_.Name) -Force }
# CN 的 4 个缩放档
foreach ($s in @("1x", "2x", "3x", "4x")) {
    $src = Join-Path $fonts "CN\$s"
    if (-not (Test-Path $src)) { continue }
    $dst = Join-Path $stage "CN\$s"
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    Get-ChildItem $src -File | Where-Object { $_.Name -like "zomboid*Chinese.*" } |
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
