# PowerShell script to force delete cdk.out folders with recursive symlinks
Write-Host "Cleaning up cdk.out folders..." -ForegroundColor Yellow

# Check both root and infrastructure directories
$searchPaths = @(".", "infrastructure")
$cdkOutFolders = @()

foreach ($path in $searchPaths) {
    $folders = Get-ChildItem -Path $path -Filter "cdk.out*" -Directory -ErrorAction SilentlyContinue
    if ($folders) {
        $cdkOutFolders += $folders
    }
}

if ($cdkOutFolders.Count -eq 0) {
    Write-Host "No cdk.out folders found!" -ForegroundColor Green
    exit 0
}

Write-Host "Found $($cdkOutFolders.Count) cdk.out folder(s)" -ForegroundColor Cyan

foreach ($folder in $cdkOutFolders) {
    Write-Host "Attempting to delete: $($folder.FullName)" -ForegroundColor Yellow
    
    $emptyDir = Join-Path $env:TEMP "empty_temp_dir"
    if (-not (Test-Path $emptyDir)) {
        New-Item -ItemType Directory -Path $emptyDir -Force | Out-Null
    }
    
    Write-Host "  Using robocopy method..." -ForegroundColor Gray
    robocopy $emptyDir $folder.FullName /MIR /R:0 /W:0 /NFL /NDL /NJH /NJS /NC /NS /NP | Out-Null
    
    try {
        Remove-Item -Path $folder.FullName -Force -ErrorAction Stop
        Write-Host "  Successfully deleted: $($folder.Name)" -ForegroundColor Green
    } catch {
        Write-Host "  Failed with Remove-Item, trying cmd..." -ForegroundColor Yellow
        cmd /c "rmdir /s /q `"$($folder.FullName)`""
        
        if (-not (Test-Path $folder.FullName)) {
            Write-Host "  Successfully deleted with cmd: $($folder.Name)" -ForegroundColor Green
        } else {
            Write-Host "  Unable to delete: $($folder.Name)" -ForegroundColor Red
        }
    }
}

if (Test-Path $emptyDir) {
    Remove-Item -Path $emptyDir -Force -ErrorAction SilentlyContinue
}

Write-Host "`nCleanup complete!" -ForegroundColor Green
