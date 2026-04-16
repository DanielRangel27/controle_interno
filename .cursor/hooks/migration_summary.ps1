$ErrorActionPreference = 'Continue'

function Read-HookInputJson {
  try {
    $raw = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($raw)) { return @{} }
    return ($raw | ConvertFrom-Json -ErrorAction Stop)
  } catch {
    return @{ __raw = $raw }
  }
}

function Get-FirstNonEmptyString([object[]]$values) {
  foreach ($v in $values) {
    if ($null -ne $v -and ($v -is [string]) -and -not [string]::IsNullOrWhiteSpace($v)) { return $v }
  }
  return $null
}

function Get-EditedFilePath($inputObj) {
  $candidates = @(
    $inputObj.path,
    $inputObj.filePath,
    $inputObj.file_path,
    $inputObj.file,
    $inputObj.arguments.path,
    $inputObj.arguments.filePath,
    $inputObj.input.path,
    $inputObj.input.filePath,
    $inputObj.context.path
  )
  $p = Get-FirstNonEmptyString $candidates
  if (-not $p) { return $null }
  try { return (Resolve-Path -LiteralPath $p).Path } catch { return $p }
}

function Summarize-Migration([string]$content) {
  $ops = @()

  if ($content -match "\bCreateModel\b") { $ops += "CreateModel" }
  if ($content -match "\bDeleteModel\b") { $ops += "DeleteModel" }
  if ($content -match "\bAddField\b") { $ops += "AddField" }
  if ($content -match "\bRemoveField\b") { $ops += "RemoveField" }
  if ($content -match "\bAlterField\b") { $ops += "AlterField" }
  if ($content -match "\bRenameField\b") { $ops += "RenameField" }
  if ($content -match "\bRenameModel\b") { $ops += "RenameModel" }
  if ($content -match "\bAddIndex\b|\bAddConstraint\b") { $ops += "AddIndex/Constraint" }
  if ($content -match "\bRemoveIndex\b|\bRemoveConstraint\b") { $ops += "RemoveIndex/Constraint" }
  if ($content -match "\bRunSQL\b") { $ops += "RunSQL" }
  if ($content -match "\bRunPython\b") { $ops += "RunPython" }

  if ($ops.Count -eq 0) { $ops = @("Operações não identificadas (migração custom?)") }

  $risks = @()
  if ($content -match "\bRunPython\b") {
    $risks += "RunPython: pode ser lento, não-idempotente e difícil de reverter; valide reversibilidade."
  }
  if ($content -match "\bRunSQL\b") {
    $risks += "RunSQL: risco de travar/timeout; confira locks, índices e compatibilidade do banco."
  }
  if ($content -match "\bAlterField\b|\bAddIndex\b|\bAddConstraint\b") {
    $risks += "AlterField/Index/Constraint: em tabela grande pode causar lock e downtime."
  }
  if ($content -match "\bRemoveField\b|\bDeleteModel\b") {
    $risks += "Remoção: possível perda de dados; avalie migração em duas fases (deprecate -> drop)."
  }

  return @{ ops = $ops; risks = $risks }
}

$inputObj = Read-HookInputJson
$filePath = Get-EditedFilePath $inputObj

if (-not $filePath -or $filePath -notmatch "(^|\\)migrations(\\).+\\.py$") {
  Write-Output "{}"
  exit 0
}

if (-not (Test-Path -LiteralPath $filePath)) {
  Write-Output "{}"
  exit 0
}

try {
  $content = Get-Content -LiteralPath $filePath -Raw -ErrorAction Stop
} catch {
  Write-Output "{}"
  exit 0
}

$sum = Summarize-Migration $content

Write-Output ""
Write-Output "=== Migração criada/alterada: $filePath ==="
Write-Output ("Resumo: " + ($sum.ops -join ", "))

if ($sum.risks.Count -gt 0) {
  Write-Output "Riscos potenciais:"
  foreach ($r in $sum.risks) { Write-Output ("- " + $r) }
} else {
  Write-Output "Riscos: nenhum padrão perigoso detectado (ainda revise antes do deploy)."
}

Write-Output "{}"
exit 0

