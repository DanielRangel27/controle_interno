$ErrorActionPreference = 'Continue'

function Read-HookInputJson {
  try {
    $raw = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($raw)) { return @{} }
    return ($raw | ConvertFrom-Json -ErrorAction Stop)
  } catch {
    return @{ }
  }
}

function Get-FirstNonEmptyString([object[]]$values) {
  foreach ($v in $values) {
    if ($null -ne $v -and ($v -is [string]) -and -not [string]::IsNullOrWhiteSpace($v)) { return $v }
  }
  return $null
}

function Get-ShellCommand($inputObj) {
  return Get-FirstNonEmptyString @(
    $inputObj.command,
    $inputObj.arguments.command,
    $inputObj.input.command
  )
}

function Exec-Capture([string]$exe, [string[]]$args) {
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $exe
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.UseShellExecute = $false
  foreach ($a in $args) { [void]$psi.ArgumentList.Add($a) }
  $p = New-Object System.Diagnostics.Process
  $p.StartInfo = $psi
  [void]$p.Start()
  $stdout = $p.StandardOutput.ReadToEnd()
  $stderr = $p.StandardError.ReadToEnd()
  $p.WaitForExit()
  return @{ code = $p.ExitCode; out = $stdout; err = $stderr }
}

function Build-DraftFromDiff([string]$diffText, [string]$statusText) {
  $files = @()
  foreach ($line in ($statusText -split "`r?`n")) {
    if ($line -match "^[ MARCUD\\?]{1,2}\\s+(.+)$") {
      $files += $Matches[1].Trim()
    }
  }
  $files = $files | Where-Object { $_ } | Select-Object -Unique
  if ($files.Count -eq 0) { $files = @("—") }

  $summaryBullets = @()
  foreach ($f in $files | Select-Object -First 6) { $summaryBullets += "- $f" }
  if ($files.Count -gt 6) { $summaryBullets += "- (mais arquivos: $($files.Count - 6))" }

  $testPlan = @(
    "- [ ] Rodar testes relevantes (ex.: `python manage.py test` ou `pytest`)",
    "- [ ] Validar fluxo principal manualmente (telas/rotas afetadas)",
    "- [ ] Se mudou models: aplicar migrações em ambiente de teste"
  )

  $body = @"
## Summary
$($summaryBullets -join "`n")

## Test plan
$($testPlan -join "`n")
"@
  return $body.TrimEnd()
}

$inputObj = Read-HookInputJson
$cmd = Get-ShellCommand $inputObj

# Best-effort git diff. If not a git repo, just allow.
$status = Exec-Capture "git" @("status", "--porcelain")
if ($status.code -ne 0) {
  Write-Output (@{ permission = "allow" } | ConvertTo-Json)
  exit 0
}

$diff = Exec-Capture "git" @("diff", "--cached")
if ($diff.code -ne 0 -or [string]::IsNullOrWhiteSpace($diff.out)) {
  # fall back to unstaged diff
  $diff = Exec-Capture "git" @("diff")
}

$draft = Build-DraftFromDiff $diff.out $status.out

$userMsg = @"
Rascunho de descrição (copie/cole no commit/PR):

$draft
"@

try {
  $json = @{
    permission = "allow"
    user_message = $userMsg
    agent_message = "Draft gerado a partir do diff/status."
  } | ConvertTo-Json -Depth 4
  Write-Output $json
} catch {
  Write-Output '{ "permission": "allow" }'
}

exit 0

