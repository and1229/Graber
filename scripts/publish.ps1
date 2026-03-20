# Публикация на GitHub + прод-деплой на Vercel (неинтерактивно).
# Секреты: переменные окружения или файл .env.publish в корне репозитория (в .gitignore).
#
# Пример .env.publish (без кавычек вокруг значений, без пробелов вокруг =):
#   GITHUB_TOKEN=ghp_xxxx
#   VERCEL_TOKEN=xxxx
#   TELEGRAM_BOT_TOKEN=опционально
#   TELEGRAM_CHAT_ID=опционально
#   GITHUB_REPO_NAME=Graber

$ErrorActionPreference = "Stop"
# Читаемый русский текст в консоли Windows (иначе «кракозябры» при cp866)
try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $OutputEncoding = [Console]::OutputEncoding
} catch {}

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Normalize-SecretValue([string]$s) {
    if ([string]::IsNullOrEmpty($s)) { return $s }
    $s = $s.Trim().Trim([char]0xFEFF)
    # невидимые пробелы / zero-width (часто при копировании из браузера)
    $s = $s -replace "[\u200B-\u200D\uFEFF]", ""
    if ($s.Length -ge 2) {
        $a, $b = $s[0], $s[$s.Length - 1]
        if (($a -eq '"' -and $b -eq '"') -or ($a -eq "'" -and $b -eq "'")) {
            $s = $s.Substring(1, $s.Length - 2).Trim()
        }
    }
    return $s.Trim()
}

function Read-DotPublish {
    $path = Join-Path $Root ".env.publish"
    if (-not (Test-Path $path)) { return }
    Get-Content $path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if ($line -match '^\s*#' -or $line -eq '') { return }
        if ($line -match '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
            $k = $matches[1]
            $v = Normalize-SecretValue $matches[2]
            if (-not [string]::IsNullOrEmpty($v)) {
                Set-Item -Path "Env:$k" -Value $v
            }
        }
    }
}

Read-DotPublish

$GithubToken = Normalize-SecretValue $env:GITHUB_TOKEN
$VercelToken = Normalize-SecretValue $env:VERCEL_TOKEN
$RepoName = if ($env:GITHUB_REPO_NAME) { $env:GITHUB_REPO_NAME } else { "Graber" }

if ([string]::IsNullOrWhiteSpace($GithubToken)) {
    Write-Host "Задайте GITHUB_TOKEN (classic: scope repo; fine-grained: Contents Read/Write + Metadata read)." -ForegroundColor Yellow
    Write-Host "Либо создайте файл $Root\.env.publish — см. комментарий в scripts\publish.ps1"
    exit 1
}
if ([string]::IsNullOrWhiteSpace($VercelToken)) {
    Write-Host "Задайте VERCEL_TOKEN: https://vercel.com/account/tokens" -ForegroundColor Yellow
    exit 1
}

$ghHeaders = @{
    Authorization        = "Bearer $GithubToken"
    Accept               = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

Write-Host "GitHub: получаю пользователя..."
$user = Invoke-RestMethod -Uri "https://api.github.com/user" -Headers $ghHeaders -Method Get
$login = $user.login
Write-Host "  логин: $login"

$repoPath = "repos/$login/$RepoName"
try {
    Invoke-RestMethod -Uri "https://api.github.com/$repoPath" -Headers $ghHeaders -Method Get | Out-Null
    Write-Host "Репозиторий $login/$RepoName уже существует."
}
catch {
    $code = $_.Exception.Response.StatusCode.value__
    if ($code -eq 404) {
        Write-Host "Создаю репозиторий $RepoName..."
        $body = @{ name = $RepoName; private = $false; auto_init = $false } | ConvertTo-Json
        Invoke-RestMethod -Uri "https://api.github.com/user/repos" -Headers $ghHeaders -Method Post -Body $body -ContentType "application/json" | Out-Null
    }
    else {
        throw
    }
}

$originHttps = "https://github.com/$login/$RepoName.git"
$pushUrl = "https://x-access-token:$GithubToken@github.com/$login/$RepoName.git"

# Не вызывать «git remote remove origin», если remote ещё нет — иначе git пишет в stderr
# и PowerShell с $ErrorActionPreference=Stop обрывает скрипт.
$hasOrigin = $false
foreach ($r in (git remote 2>$null)) { if ($r -eq "origin") { $hasOrigin = $true; break } }
if ($hasOrigin) {
    git remote set-url origin $originHttps
} else {
    git remote add origin $originHttps
}
if ($LASTEXITCODE -ne 0) { throw "git remote: не удалось настроить origin (код $LASTEXITCODE)" }

Write-Host "Git push -> $originHttps"
$env:GIT_TERMINAL_PROMPT = "0"
git push $pushUrl HEAD:main
if ($LASTEXITCODE -ne 0) { throw "git push завершился с кодом $LASTEXITCODE" }

git branch -M main 2>$null
git config branch.main.remote origin
git config branch.main.merge refs/heads/main

Write-Host "Vercel: прод-деплой..."
$npx = "npx"
& $npx --yes vercel@latest deploy --prod --yes --token $VercelToken --cwd $Root
if ($LASTEXITCODE -ne 0) { throw "vercel deploy завершился с кодом $LASTEXITCODE" }

$tTok = Normalize-SecretValue $env:TELEGRAM_BOT_TOKEN
$tChat = Normalize-SecretValue $env:TELEGRAM_CHAT_ID
if (-not [string]::IsNullOrWhiteSpace($tTok) -and -not [string]::IsNullOrWhiteSpace($tChat)) {
    Write-Host "Vercel: добавляю TELEGRAM_* в Production..."
    & $npx --yes vercel@latest env add TELEGRAM_BOT_TOKEN production --value $tTok --yes --token $VercelToken --cwd $Root
    & $npx --yes vercel@latest env add TELEGRAM_CHAT_ID production --value $tChat --yes --token $VercelToken --cwd $Root
    Write-Host "Перезапускаю прод-деплой с переменными..."
    & $npx --yes vercel@latest deploy --prod --yes --token $VercelToken --cwd $Root
}

Write-Host ""
Write-Host "Готово. Репозиторий: https://github.com/$login/$RepoName" -ForegroundColor Green
Write-Host "Если TELEGRAM_* не задавали в .env.publish — добавьте их в Vercel: Project -> Settings -> Environment Variables -> Production, затем Redeploy." -ForegroundColor Cyan
