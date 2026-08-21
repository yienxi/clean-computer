# restore_windows.ps1 — 从 manifest 一键回滚清理动作（v1.5，Windows）
# 读取 %USERPROFILE%\.clean-computer\manifest.jsonl，把记录中 status=moved 的项从回收站恢复。
# 安全约束：
#   1) 仅恢复 status=moved 记录；status=emptied（清空回收站）不可恢复，仅展示。
#   2) 原路径已存在则跳过（避免覆盖现有文件）。
#   3) 恢复后标记 status=restored（重建 manifest，保留审计）。
# 用法:
#   restore_windows.ps1                # 预览所有可恢复项
#   restore_windows.ps1 -All           # 恢复所有可恢复项
#   restore_windows.ps1 -Category temp # 仅预览某品类（配合 -All 恢复）
#   restore_windows.ps1 -DryRun        # 仅预览不恢复
param(
  [switch]$All,
  [string]$Category = "",
  [switch]$DryRun
)

$manifestDir = Join-Path $env:USERPROFILE ".clean-computer"
$manifest    = Join-Path $manifestDir "manifest.jsonl"

if (-not (Test-Path $manifest)) { Write-Host "无 manifest（$manifest），没有可恢复的清理记录。"; exit 0 }

$shell   = New-Object -ComObject Shell.Application
$recycle = $shell.NameSpace(10)  # Recycle Bin 命名空间

# 读取 moved 记录
$lines = Get-Content $manifest | Where-Object { $_ -match '"status":"moved"' }
$emptied = Get-Content $manifest | Where-Object { $_ -match '"status":"emptied"' }

Write-Host "=== 可恢复项（status=moved）==="
$matched = @()
foreach ($line in $lines) {
  $row = $line | ConvertFrom-Json
  if ($Category -and $row.category -ne $Category) { continue }
  # 在回收站中查找对应项（按原路径匹配）
  $found = $false
  foreach ($item in $recycle.Items()) {
    $deletedFrom = $item.ExtendedProperty("System.Recycle.DeletedFrom")
    if ($deletedFrom -eq $row.src) { $found = $true; break }
  }
  if ($found) {
    Write-Host ("  [{0}] {1}" -f $row.category, $row.src)
    $matched += $row
  } else {
    Write-Host ("  [{0}] {1}  （回收站中已找不到该项，跳过）" -f $row.category, $row.src)
    $row.status = "restored"   # 无实体可恢复，标记 restored 保留审计
    $matched += $row
  }
}
foreach ($line in $emptied) {
  $row = $line | ConvertFrom-Json
  Write-Host ("  (审计) {0} 清空回收站 —— 不可恢复" -f $row.ts)
}

if ($DryRun -or -not $All) {
  Write-Host ""
  Write-Host "以上为预览。真正恢复请加 -All（或 -Category <品类> -All）。"
  exit 0
}

Write-Host ""
Write-Host "=== 开始恢复（原路径已存在则跳过，避免覆盖）==="
$restored = 0
$updated = @()
foreach ($row in $matched) {
  if (Test-Path $row.src) {
    Write-Host ("  ✗ 跳过（原路径已存在）: {0}" -f $row.src)
    $updated += ($row | ConvertTo-Json -Compress -Depth 3)
    continue
  }
  $target = $null
  foreach ($item in $recycle.Items()) {
    $deletedFrom = $item.ExtendedProperty("System.Recycle.DeletedFrom")
    if ($deletedFrom -eq $row.src) { $target = $item; break }
  }
  if ($target) {
    try {
      $target.InvokeVerb("restore")
      Write-Host ("  ✓ 已恢复: {0}" -f $row.src)
      $row.status = "restored"
      $restored++
    } catch {
      Write-Host ("  ✗ 恢复失败: {0}  ({1})" -f $row.src, $_.Exception.Message)
    }
  } else {
    Write-Host ("  (回收站中已找不到该项，标记 restored) {0}" -f $row.src)
    $row.status = "restored"
  }
  $updated += ($row | ConvertTo-Json -Compress -Depth 3)
}

# 保留非 moved/emptied 记录（其他品类/已处理），合并重建 manifest
$keep = Get-Content $manifest | Where-Object { $_ -notmatch '"status":"moved"' -and $_ -notmatch '"status":"emptied"' }
$keep + $updated | Where-Object { $_ } | Set-Content -Path $manifest -Encoding UTF8
Write-Host ("  完成: 恢复 {0} 项。" -f $restored)
Write-Host "=== 恢复完成。manifest 已标记 status=restored（审计保留）==="
