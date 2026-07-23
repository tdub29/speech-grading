<#
.SYNOPSIS
  Grade any transcript with orator and circle the result back to one place.

.DESCRIPTION
  One command any project (or agent) can call on a transcript of spoken delivery.
  It writes a report next to the source, appends a one-line row to the central
  grading ledger, and emits the word-choice request packet so an agent (Claude in
  the loop) can add better-word / tripped-up findings without an API key.

.EXAMPLE
  pwsh orate.ps1 path\to\answer.txt
  # an agent fills <answer.txt>.llm-request.json -> <answer.txt>.llm-response.json
  pwsh orate.ps1 path\to\answer.txt -WordChoice path\to\answer.txt.llm-response.json
#>
param(
  [Parameter(Mandatory = $true)] [string] $Transcript,
  [string] $WordChoice,   # agent-filled response JSON to merge
  [string] $Log           # central ledger (defaults to speech-grading/graded-log.md)
)

$ErrorActionPreference = "Stop"
$env:VIRTUAL_ENV = $null; $env:PYTHONHOME = $null; $env:PYTHONPATH = $null

# Resolve this script's directory (works under both pwsh and Windows PowerShell).
$scriptDir = $PSScriptRoot
if (-not $scriptDir) { $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $Log) { $Log = Join-Path $scriptDir "graded-log.md" }

$orator = Join-Path $scriptDir ".venv\Scripts\orator.exe"
if (-not (Test-Path $orator)) {
  Write-Error "orator venv not found. From $scriptDir run: uv venv .venv; uv pip install -e ."
  exit 1
}

$html = "$Transcript.orator.html"
$json = "$Transcript.orator.json"

$oratorArgs = @($Transcript, "--html", $html, "--json", $json, "--log", $Log)
if ($WordChoice) {
  $oratorArgs += @("--wordchoice-json", $WordChoice)   # merge agent findings
} else {
  $oratorArgs += "--emit-request"                      # ask an agent to enrich
}

& $orator @oratorArgs
Write-Host "report: $html"
Write-Host "ledger: $Log"
