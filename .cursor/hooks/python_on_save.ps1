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

function Get-RepoRoot {
  try {
    $here = (Get-Location).Path
    return $here
  } catch {
    return $PSScriptRoot
  }
}

function Get-StableKeyForPath([string]$path) {
  $sha1 = [System.Security.Cryptography.SHA1]::Create()
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($path.ToLowerInvariant())
  $hash = $sha1.ComputeHash($bytes)
  return ($hash | ForEach-Object { $_.ToString('x2') }) -join ''
}

function Should-SkipDueToRecentRun([string]$filePath, [int]$windowSeconds = 3) {
  $root = Get-RepoRoot
  $cacheDir = Join-Path $root ".cursor/hooks/.cache"
  New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null

  $key = Get-StableKeyForPath $filePath
  $stampPath = Join-Path $cacheDir "$key.stamp"
  $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()

  if (Test-Path -LiteralPath $stampPath) {
    try {
      $last = [int64](Get-Content -LiteralPath $stampPath -ErrorAction Stop | Select-Object -First 1)
      if (($now - $last) -le $windowSeconds) { return $true }
    } catch {}
  }

  try { Set-Content -LiteralPath $stampPath -Value $now -Encoding ascii -Force } catch {}
  return $false
}

function Exec-Cmd([string]$exe, [string[]]$args, [string]$workingDir) {
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $exe
  $psi.WorkingDirectory = $workingDir
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
  return @{
    exitCode = $p.ExitCode
    stdout   = $stdout
    stderr   = $stderr
  }
}

$inputObj = Read-HookInputJson
$filePath = Get-EditedFilePath $inputObj

if (-not $filePath) {
  Write-Output "[hook python_on_save] Não consegui identificar o caminho do arquivo no input do hook."
  Write-Output "{}"
  exit 0
}

if ($filePath -notmatch "\.py$") {
  Write-Output "{}"
  exit 0
}

if (Should-SkipDueToRecentRun $filePath) {
  Write-Output "{}"
  exit 0
}

$root = Get-RepoRoot

Write-Output ""
Write-Output "=== onSave: $filePath ==="

# 1) Ruff lint
try {
  $res = Exec-Cmd "ruff" @("check", "--force-exclude", $filePath) $root
  if (-not [string]::IsNullOrWhiteSpace($res.stdout)) { Write-Output $res.stdout.TrimEnd() }
  if (-not [string]::IsNullOrWhiteSpace($res.stderr)) { Write-Output $res.stderr.TrimEnd() }
  if ($res.exitCode -ne 0) { Write-Output "[ruff check] exitCode=$($res.exitCode)" }
} catch {
  Write-Output "[ruff check] Ruff não está disponível no PATH. Instale com: python -m pip install ruff"
}

# 2) Ruff format (Black-like)
try {
  $res = Exec-Cmd "ruff" @("format", "--force-exclude", $filePath) $root
  if (-not [string]::IsNullOrWhiteSpace($res.stdout)) { Write-Output $res.stdout.TrimEnd() }
  if (-not [string]::IsNullOrWhiteSpace($res.stderr)) { Write-Output $res.stderr.TrimEnd() }
  if ($res.exitCode -ne 0) { Write-Output "[ruff format] exitCode=$($res.exitCode)" }
} catch {
  Write-Output "[ruff format] Ruff não está disponível no PATH. Instale com: python -m pip install ruff"
}

# 3) Django-specific hints
$leaf = [System.IO.Path]::GetFileName($filePath)

if ($leaf -ieq "models.py") {
  Write-Output ""
  Write-Output "Sugestão (Django): você alterou models.py."
  Write-Output "Você quer rodar: python manage.py makemigrations ?"
  Write-Output "Impactos comuns:"
  Write-Output "- Criará/alterará migrações; isso afeta deploy (ordem de execução, locks)."
  Write-Output "- AlterField/Index em tabela grande pode ser pesado e causar indisponibilidade."
  Write-Output "- Remoção/rename sem estratégia pode causar perda de dados."
  try {
    $dry = Exec-Cmd "python" @("manage.py", "makemigrations", "--dry-run", "--check") $root
    if ($dry.exitCode -ne 0) {
      if (-not [string]::IsNullOrWhiteSpace($dry.stdout)) { Write-Output $dry.stdout.TrimEnd() }
      if (-not [string]::IsNullOrWhiteSpace($dry.stderr)) { Write-Output $dry.stderr.TrimEnd() }
    } else {
      Write-Output "Dica: 'makemigrations --dry-run --check' não encontrou mudanças pendentes."
    }
  } catch {
    Write-Output "Obs.: não consegui executar python/manage.py aqui (verifique venv/PATH)."
  }
}

if ($leaf -ieq "views.py" -or $leaf -ieq "urls.py") {
  Write-Output ""
  Write-Output "Checagens rápidas (Django): você alterou $leaf."
  try {
    $pyc = Exec-Cmd "python" @("-m", "py_compile", $filePath) $root
    if ($pyc.exitCode -ne 0) {
      Write-Output "[py_compile] Possível erro de sintaxe/import:"
      if (-not [string]::IsNullOrWhiteSpace($pyc.stderr)) { Write-Output $pyc.stderr.TrimEnd() }
      if (-not [string]::IsNullOrWhiteSpace($pyc.stdout)) { Write-Output $pyc.stdout.TrimEnd() }
    } else {
      Write-Output "[py_compile] OK (sintaxe/import básico)."
    }
  } catch {
    Write-Output "Obs.: não consegui executar python para py_compile (verifique venv/PATH)."
  }

  Write-Output "Sugestões para evitar rotas não registradas:"
  Write-Output "- Confirme que o app está incluído em controle_interno/urls.py (include(...))."
  Write-Output "- Se criou nova view, garanta que está em urlpatterns e que o import não ficou quebrado."
}

Write-Output "{}"
exit 0

