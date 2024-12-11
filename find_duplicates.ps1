# Define the search patterns
$patterns = @(
    '@main_bp.route\s*\(\s*[''"]\/upload[''"]',
    '@bp.route\s*\(\s*[''"]\/upload[''"]',
    'def\s+upload\s*\(',
    'def\s+allowed_file\s*\(',
    '@main.route\s*\(\s*[''"]\/upload[''"]'
)

# Create the search pattern string
$patternString = $patterns -join '|'

Write-Host "`nSearching for potential duplicate route definitions...`n" -ForegroundColor Yellow

# Search through all Python files
Get-ChildItem -Path . -Filter "*.py" -Recurse | ForEach-Object {
    $file = $_
    $lineNumber = 0
    $foundMatch = $false
    
    Get-Content $file | ForEach-Object {
        $lineNumber++
        if ($_ -match $patternString) {
            if (-not $foundMatch) {
                Write-Host "File: $($file.FullName)" -ForegroundColor Cyan
                $foundMatch = $true
            }
            Write-Host "Line $lineNumber : $_" -ForegroundColor Green
        }
    }
    if ($foundMatch) {
        Write-Host "`n"
    }
}

# Search for blueprint registrations
Write-Host "Searching for blueprint registrations...`n" -ForegroundColor Yellow

Get-ChildItem -Path . -Filter "*.py" -Recurse | ForEach-Object {
    $file = $_
    $lineNumber = 0
    $foundMatch = $false
    
    Get-Content $file | ForEach-Object {
        $lineNumber++
        if ($_ -match 'register_blueprint|Blueprint\(') {
            if (-not $foundMatch) {
                Write-Host "File: $($file.FullName)" -ForegroundColor Cyan
                $foundMatch = $true
            }
            Write-Host "Line $lineNumber : $_" -ForegroundColor Green
        }
    }
    if ($foundMatch) {
        Write-Host "`n"
    }
}

# Search for imported route modules
Write-Host "Searching for route imports...`n" -ForegroundColor Yellow

Get-ChildItem -Path . -Filter "*.py" -Recurse | ForEach-Object {
    $file = $_
    $lineNumber = 0
    $foundMatch = $false
    
    Get-Content $file | ForEach-Object {
        $lineNumber++
        if ($_ -match 'from.*routes.*import|import.*routes') {
            if (-not $foundMatch) {
                Write-Host "File: $($file.FullName)" -ForegroundColor Cyan
                $foundMatch = $true
            }
            Write-Host "Line $lineNumber : $_" -ForegroundColor Green
        }
    }
    if ($foundMatch) {
        Write-Host "`n"
    }
}

Write-Host "Search complete. Review the findings above to identify duplicate route definitions." -ForegroundColor Yellow