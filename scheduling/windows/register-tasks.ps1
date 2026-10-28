# Register the engine's schedules in Windows Task Scheduler, running inside WSL.
#   powershell -ExecutionPolicy Bypass -File register-tasks.ps1 [-Apply] [-DryRunCommands] [-Remove]
# Default prints what it would do. Reads ..\jobs.txt. Times are Windows local time.
param([switch]$Apply, [switch]$DryRunCommands, [switch]$Remove,
      [string]$Distro = "", [string]$RepoPath = "")
$ErrorActionPreference = "Stop"
$jobsFile = Join-Path $PSScriptRoot "..\jobs.txt"
if (-not $RepoPath) {
  $RepoPath = (wsl.exe -e bash -lc "wslpath -a '$((Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path)'").Trim()
}
$days = @{ "0"="Sunday"; "1"="Monday"; "2"="Tuesday"; "3"="Wednesday"; "4"="Thursday"; "5"="Friday"; "6"="Saturday"; "7"="Sunday" }
foreach ($line in Get-Content $jobsFile) {
  if ($line -match '^\s*(#|$)') { continue }
  $name, $when, $cmd = $line.Split('|') | ForEach-Object { $_.Trim() }
  $m, $h, $d = $when -split '\s+'
  if ($DryRunCommands) { $cmd = $cmd -replace '\s--apply', '' }
  $task = "ContentEngine-$name"
  if ($Remove) {
    if ($Apply) { Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction SilentlyContinue; "removed $task" }
    else { "would remove $task" }
    continue
  }
  $distroArg = if ($Distro) { "-d $Distro " } else { "" }
  $action = New-ScheduledTaskAction -Execute "wsl.exe" -Argument "$distroArg-e bash -lc `"'$RepoPath/scheduling/run.sh' $cmd`""
  $at = [datetime]::Today.AddHours([int]$h).AddMinutes([int]$m)
  $trigger = if ($d -eq "*") { New-ScheduledTaskTrigger -Daily -At $at } else { New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days[$d] -At $at }
  if ($Apply) {
    Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger -Force | Out-Null
    "registered $task  ($when)  $cmd"
  } else { "would register $task  ($when)  wsl.exe $($action.Arguments)" }
}
if (-not $Apply) { "(dry-run: nothing registered. Add -Apply to register.)" }
