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

function Get-ShellCommand($inputObj) {
  return Get-FirstNonEmptyString @(
    $inputObj.command,
    $inputObj.arguments.command,
    $inputObj.input.command,
    $inputObj.tool_input.command
  )
}

function Get-ToolOutputText($inputObj) {
  # Best-effort: different Cursor versions serialize tool output differently.
  $out = Get-FirstNonEmptyString @(
    $inputObj.output,
    $inputObj.tool_output,
    $inputObj.error,
    $inputObj.message
  )
  if ($out) { return $out }

  try {
    return ($inputObj | ConvertTo-Json -Depth 8)
  } catch {
    return ""
  }
}

function LooksLikeTestCommand([string]$cmd) {
  if (-not $cmd) { return $false }
  return ($cmd -match "(^|\\s)(pytest|python\\s+-m\\s+pytest|python\\s+manage\\.py\\s+test|manage\\.py\\s+test)(\\s|$)")
}

function Tail-Lines([string]$text, [int]$maxLines = 200) {
  if ([string]::IsNullOrEmpty($text)) { return "" }
  $lines = $text -split "`r?`n"
  if ($lines.Length -le $maxLines) { return $text.TrimEnd() }
  return (($lines | Select-Object -Last $maxLines) -join "`n").TrimEnd()
}

$inputObj = Read-HookInputJson
$cmd = Get-ShellCommand $inputObj

if (-not (LooksLikeTestCommand $cmd)) {
  # Not a test failure we care about.
  Write-Output "{}"
  exit 0
}

$outText = Get-ToolOutputText $inputObj
$tail = Tail-Lines $outText 200

$context = @"
Teste falhou. Abaixo está o final do output/traceback (últimas ~200 linhas).

Tarefa para a IA:
- Proponha **2–3 hipóteses** (com sinais/contra-sinais no traceback)
- Sugira um **patch mínimo** (arquivos e mudanças) para a hipótese mais provável

Comando: $cmd

--- traceback/output (tail) ---
$tail
"@

# postToolUseFailure suporta additional_context (de acordo com o guia do projeto).
try {
  $json = @{ additional_context = $context } | ConvertTo-Json -Depth 4
  Write-Output $json
} catch {
  Write-Output "{ }"
}

exit 0

