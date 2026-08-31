param(
    [switch]$FromClipboard
)

$ErrorActionPreference = "Stop"

$pointer = [IntPtr]::Zero
$plainKey = $null
try {
    if ($FromClipboard) {
        Write-Host "Copy the new Tavily key in your browser now, then return here and press Enter." -ForegroundColor Cyan
        Read-Host "Waiting for the copied key" | Out-Null
        try {
            $plainKey = [string](Get-Clipboard -Raw)
        }
        catch {
            throw "Cannot read the clipboard. Copy the Tavily key first, then run this command again."
        }
    }
    else {
        Write-Host "Paste the new Tavily API key, then press Enter." -ForegroundColor Cyan
        Write-Host "The key is hidden while you type and is not written to command history." -ForegroundColor DarkGray
        $secureKey = Read-Host "API key" -AsSecureString
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
        $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }

    if ([string]::IsNullOrWhiteSpace($plainKey) -or -not $plainKey.StartsWith("tvly-")) {
        throw "Invalid Tavily key. Paste the newly created key that starts with tvly-."
    }

    $requestBody = @{
        query = "Tavily API connection test"
        search_depth = "basic"
        include_answer = $false
        max_results = 1
    } | ConvertTo-Json -Compress

    try {
        $response = Invoke-RestMethod `
            -Uri "https://api.tavily.com/search" `
            -Method Post `
            -Headers @{ Authorization = "Bearer $plainKey" } `
            -ContentType "application/json" `
            -Body $requestBody `
            -TimeoutSec 20
        if ($null -eq $response.results -or $response.results.Count -lt 1) {
            throw "No result returned"
        }
    }
    catch {
        throw "Tavily validation failed. The key was not saved. Check the new key and try again."
    }

    [Environment]::SetEnvironmentVariable("TAVILY_API_KEY", $plainKey, "User")
    Write-Host "Tavily connection verified and key saved to your user environment." -ForegroundColor Green
    Write-Host "Fully close YOUFFICE, then start it again." -ForegroundColor Yellow
}
finally {
    if ($pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
    $plainKey = $null
}
