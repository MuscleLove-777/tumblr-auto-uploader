[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param(
    [string]$TaskName = 'MuscleLove_Tumblr_LocalDispatch'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RunnerPath = 'C:\ML40_social\tumblr-auto-uploader\run_local_dispatch.cmd'
$PythonPath = 'C:\Users\atsus\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$WorkingDirectory = Split-Path -Parent $RunnerPath
$CmdExe = Join-Path $env:SystemRoot 'System32\cmd.exe'
$TaskPath = '\'
$Description = 'Managed by MuscleLove tumblr-auto-uploader/install_scheduled_task.ps1; dispatches one approved local video.'

foreach ($RequiredPath in @($RunnerPath, $PythonPath)) {
    if (-not (Test-Path -LiteralPath $RequiredPath -PathType Leaf)) {
        throw "必須ファイルが見つかりません: $RequiredPath"
    }
}

$Existing = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue
if ($null -ne $Existing) {
    $ExpectedAction = $false
    foreach ($ExistingAction in @($Existing.Actions)) {
        $ExecuteMatches = [string]::Equals(
            [string]$ExistingAction.Execute,
            $CmdExe,
            [System.StringComparison]::OrdinalIgnoreCase
        ) -or [string]::Equals(
            [string]$ExistingAction.Execute,
            'cmd.exe',
            [System.StringComparison]::OrdinalIgnoreCase
        )
        $ArgumentsContainRunner = ([string]$ExistingAction.Arguments).IndexOf(
            $RunnerPath,
            [System.StringComparison]::OrdinalIgnoreCase
        ) -ge 0
        if ($ExecuteMatches -and $ArgumentsContainRunner) {
            $ExpectedAction = $true
            break
        }
    }
    $ManagedDescription = ([string]$Existing.Description).StartsWith(
        'Managed by MuscleLove tumblr-auto-uploader/',
        [System.StringComparison]::Ordinal
    )
    $LegacyDescription = ([string]$Existing.Description).StartsWith(
        'Dispatch one unposted video from 001_',
        [System.StringComparison]::Ordinal
    )
    if (-not ($ExpectedAction -or $ManagedDescription -or $LegacyDescription)) {
        throw "同名の未管理タスクを検出したため更新を中止しました: $TaskPath$TaskName"
    }
}

function New-NextDailyTrigger([int]$Hour, [int]$Minute) {
    $Now = Get-Date
    $FirstRun = $Now.Date.AddHours($Hour).AddMinutes($Minute)
    if ($FirstRun -le $Now) {
        $FirstRun = $FirstRun.AddDays(1)
    }
    return New-ScheduledTaskTrigger -Daily -At $FirstRun
}

$Action = New-ScheduledTaskAction `
    -Execute $CmdExe `
    -Argument "/d /c `"`"$RunnerPath`"`"" `
    -WorkingDirectory $WorkingDirectory
$Triggers = @(
    (New-NextDailyTrigger -Hour 2 -Minute 0),
    (New-NextDailyTrigger -Hour 14 -Minute 0),
    (New-NextDailyTrigger -Hour 20 -Minute 0)
)
$Principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -WakeToRun `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)
$Task = New-ScheduledTask `
    -Action $Action `
    -Trigger $Triggers `
    -Principal $Principal `
    -Settings $Settings `
    -Description $Description

if (-not $PSCmdlet.ShouldProcess("$TaskPath$TaskName", '02:00/14:00/20:00 JSTの有効タスクとして登録または更新')) {
    return
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -TaskPath $TaskPath `
    -InputObject $Task `
    -Force | Out-Null
Enable-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath | Out-Null

$Verified = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath
$Info = Get-ScheduledTaskInfo -TaskName $TaskName -TaskPath $TaskPath
if ([string]$Verified.State -eq 'Disabled') {
    throw "登録後の有効化を確認できませんでした: $TaskPath$TaskName"
}
if (@($Verified.Triggers).Count -ne 3) {
    throw "登録後のトリガー数が不正です: $(@($Verified.Triggers).Count)"
}
if ($Info.NextRunTime -le (Get-Date)) {
    throw "次回実行時刻が未来ではありません: $($Info.NextRunTime)"
}

Write-Output "TASK_REGISTERED_READY: $TaskPath$TaskName / next=$($Info.NextRunTime.ToString('yyyy-MM-dd HH:mm:ss')) JST"
