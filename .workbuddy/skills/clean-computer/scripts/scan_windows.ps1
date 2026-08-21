# scan_windows.ps1 — 只读扫描 Windows 可清理项
# 安全：仅统计大小与路径，绝不删除。
$ErrorActionPreference = "SilentlyContinue"

Write-Host "=== Windows 清理扫描报告（只读，不修改任何文件）==="

$spots = @(
  @{n="用户临时";  p="$env:LOCALAPPDATA\Temp"},
  @{n="系统临时";  p="C:\Windows\Temp"},
  @{n="Edge缓存";  p="$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Cache"},
  @{n="Chrome缓存";p="$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Cache"},
  @{n="微信缓存";  p="$env:LOCALAPPDATA\Tencent\WeChat"},
  @{n="更新缓存";  p="C:\Windows\SoftwareDistribution\Download"}
)

foreach ($s in $spots) {
  if (Test-Path $s.p) {
    $bytes = (Get-ChildItem $s.p -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    $mb = [math]::Round($bytes / 1MB, 1)
    Write-Host ("  [{0,-10}] {1}`n       大小: {2} MB" -f $s.n, $s.p, $mb)
  } else {
    Write-Host ("  [{0,-10}] {1} — 不存在，跳过" -f $s.n, $s.p)
  }
}

Write-Host ""
Write-Host "=== 回收站 ==="
$shell = New-Object -ComObject Shell.Application
$bin = $shell.NameSpace(10)
if ($bin) { Write-Host ("  回收站项数: {0}" -f $bin.Items().Count) }

Write-Host ""
Write-Host "=== 扫描完成。清理请用 clean_windows.ps1 -Category <品类> 先看预览，确认后加 -Confirm ==="
