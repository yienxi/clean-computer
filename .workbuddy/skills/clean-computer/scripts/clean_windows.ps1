# clean_windows.ps1 — 引导式 Windows 清理（默认 WhatIf 仅预览；删除需 -Confirm）
# v1.5 安全机制（对齐 macOS 端）：
#   1) 仅处理"可恢复的安全子路径"，绝不含 桌面/下载/文档/用户目录根/系统根。
#   2) 送回收站(Recycle Bin)而非永久删除，删除可逆。
#   3) 单批最多 10 项，超出需再次运行。
#   4) 任何删除前先预览路径与大小，并要求 y/N 确认。
#   5) manifest 清理日志（%USERPROFILE%\.clean-computer\manifest.jsonl），支持一键回滚 restore_windows.ps1。
#   6) 程序化风险门禁：仅接受白名单精确路径，未知品类直接拒绝。
#   7) 幂等：已清理且路径不存在则安全跳过。
param(
  [string]$Category = "",
  [switch]$Confirm
)

# 白名单：品类 → 精确路径数组（程序化风险门禁基础）
$catDefs = @{
  temp      = @("$env:LOCALAPPDATA\Temp", "C:\Windows\Temp")
  edge      = @("$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Cache")
  chrome    = @("$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Cache")
  wechat    = @("$env:LOCALAPPDATA\Tencent\WeChat")
  winupdate = @("C:\Windows\SoftwareDistribution\Download")
}

$manifestDir = Join-Path $env:USERPROFILE ".clean-computer"
$manifest    = Join-Path $manifestDir "manifest.jsonl"

if (-not $Category) { Write-Host "请指定 -Category: temp edge chrome wechat winupdate"; exit 1 }
if (-not $catDefs.ContainsKey($Category)) { Write-Host "✗ 风险门禁拒绝：未知品类 '$Category'"; exit 1 }
$targets = $catDefs[$Category]

$shell   = New-Object -ComObject Shell.Application
$recycle = $shell.NameSpace(10)  # Recycle Bin 命名空间

if (-not $Confirm) {
  Write-Host "=== WhatIf 预览（不删除）==="
  Write-Host "  [风险门禁] 目标须精确命中白名单"
  foreach ($t in $targets) {
    if (Test-Path $t) {
      $bytes = (Get-ChildItem $t -Recurse -EA SilentlyContinue | Measure-Object Length -Sum).Sum
      $mb = [math]::Round($bytes / 1MB, 1)
      Write-Host ("  [{0}] {1}  ({2} MB)" -f $Category, $t, $mb)
    } else { Write-Host ("  [{0}] {1} 不存在" -f $Category, $t) }
  }
  Write-Host "确认请加 -Confirm（送回收站，可恢复；记录于 manifest 支持回滚）。"
  exit 0
}

# 幂等：该品类全部目标路径均不存在且 manifest 有 moved 记录 → 提示
$allMissing = $true
foreach ($t in $targets) { if (Test-Path $t) { $allMissing = $false; break } }
if ($allMissing -and (Test-Path $manifest)) {
  $hit = Select-String -Path $manifest -Pattern ('"category":"' + $Category + '"') -EA SilentlyContinue
  if ($hit) { Write-Host "  幂等提示: '$Category' 已按 manifest 记录清理过，且路径不存在。若为新产生的缓存，重新运行即可（会再次记录）。" }
}

Write-Host "⚠️ 即将送回收站(可恢复)："
$n = 0
foreach ($t in $targets) { if (Test-Path $t) { Write-Host "  - $t"; $n++ } }
if ($n -eq 0) { Write-Host "无目标可处理。"; exit 0 }

$ans = Read-Host "确认执行? (y/N)"
if ($ans -ne "y") { Write-Host "已取消。"; exit 0 }

if (-not (Test-Path $manifestDir)) { New-Item -ItemType Directory -Path $manifestDir -Force | Out-Null }

$i = 0
foreach ($t in $targets) {
  if (Test-Path $t) {
    try {
      $recycle.MoveHere($t)
      $size = (Get-ChildItem $t -Recurse -EA SilentlyContinue | Measure-Object Length -Sum).Sum
      # 回收站内同名项会加后缀；dest 记录为原名（供 restore 按原路径匹配）
      $ts = Get-Date -Format "yyyy-MM-ddTHH:mm:sszzz"
      $row = '{"ts":"{0}","category":"{1}","src":"{2}","dest":"(recycle)","size_bytes":{3},"status":"moved"}' -f $ts, $Category, ($t -replace '"', '\"'), $size
      Add-Content -Path $manifest -Value $row -Encoding UTF8
      Write-Host ("  ✓ 已送回收站(可恢复): {0}" -f $t)
      $i++
      if ($i -ge 10) { Write-Host "  已达单批上限 10 项，剩余请再次运行。"; break }
    } catch {
      Write-Host ("  ✗ 移动失败，已跳过未删除: {0}  ({1})" -f $t, $_.Exception.Message)
    }
  }
}
Write-Host "=== 完成。回滚请运行: restore_windows.ps1 -Category $Category -All ==="
