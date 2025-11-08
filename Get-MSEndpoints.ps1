#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Fetches Microsoft 365 endpoints and creates firewall list files.

.DESCRIPTION
    This script fetches Microsoft 365 endpoints from the official Microsoft API
    and generates list files that can be used in firewall configurations.
    Files are named: ms365_{{addrType}}_{{category}}_{{serviceArea}}.txt
    where:
    - addrType: url, ipv4, ipv6
    - category: opt, allow, default
    - serviceArea: common, exchange, sharepoint, teams, etc.

.PARAMETER OutputDirectory
    Directory where the list files will be saved. Default is './lists'

.PARAMETER ClientRequestId
    Optional client request ID for API tracking. A random GUID is generated if not provided.

.EXAMPLE
    .\Get-MSEndpoints.ps1
    .\Get-MSEndpoints.ps1 -OutputDirectory "./output"
#>

param(
    [Parameter(Mandatory = $false)]
    [string]$OutputDirectory = "./lists",
    
    [Parameter(Mandatory = $false)]
    [string]$ClientRequestId = [guid]::NewGuid().ToString()
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Create output directory if it doesn't exist
if (-not (Test-Path -Path $OutputDirectory)) {
    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
    Write-Host "Created output directory: $OutputDirectory"
}

# Fetch endpoints from Microsoft API
$apiUrl = "https://endpoints.office.com/endpoints/worldwide?clientrequestid=$ClientRequestId"
Write-Host "Fetching endpoints from: $apiUrl"

try {
    $endpoints = Invoke-RestMethod -Uri $apiUrl -Method Get
    Write-Host "Successfully fetched $($endpoints.Count) endpoint entries"
}
catch {
    Write-Error "Failed to fetch endpoints: $_"
    exit 1
}

# Initialize hashtable to group data
$groupedData = @{}

# Process each endpoint
foreach ($endpoint in $endpoints) {
    # Determine category (Optimize=opt, Allow=allow, Default=default)
    $category = switch ($endpoint.category) {
        "Optimize" { "opt" }
        "Allow" { "allow" }
        "Default" { "default" }
        default { "default" }
    }
    
    # Get service area (normalize to lowercase)
    $serviceArea = if ($endpoint.serviceArea) { 
        $endpoint.serviceArea.ToLower() 
    } else { 
        "common" 
    }
    
    # Process URLs
    if ($endpoint.urls) {
        $key = "url_${category}_${serviceArea}"
        if (-not $groupedData.ContainsKey($key)) {
            $groupedData[$key] = @()
        }
        foreach ($url in $endpoint.urls) {
            if ($url -and $url.Trim() -ne "") {
                $groupedData[$key] += $url
            }
        }
    }
    
    # Process IPv4 addresses
    if ($endpoint.ips) {
        foreach ($ip in $endpoint.ips) {
            # Check if it's IPv4 (contains dots but not colons)
            if ($ip -match '^\d+\.\d+\.\d+\.\d+' -and $ip -notmatch ':') {
                $key = "ipv4_${category}_${serviceArea}"
                if (-not $groupedData.ContainsKey($key)) {
                    $groupedData[$key] = @()
                }
                if ($ip -and $ip.Trim() -ne "") {
                    $groupedData[$key] += $ip
                }
            }
            # Check if it's IPv6 (contains colons)
            elseif ($ip -match ':') {
                $key = "ipv6_${category}_${serviceArea}"
                if (-not $groupedData.ContainsKey($key)) {
                    $groupedData[$key] = @()
                }
                if ($ip -and $ip.Trim() -ne "") {
                    $groupedData[$key] += $ip
                }
            }
        }
    }
}

# Write data to files
$fileCount = 0
foreach ($key in $groupedData.Keys | Sort-Object) {
    # Remove duplicates and sort
    $uniqueData = $groupedData[$key] | Select-Object -Unique | Sort-Object
    
    if ($uniqueData.Count -gt 0) {
        $fileName = "ms365_$key.txt"
        $filePath = Join-Path -Path $OutputDirectory -ChildPath $fileName
        
        # Write to file
        $uniqueData | Out-File -FilePath $filePath -Encoding UTF8 -Force
        
        Write-Host "Created: $fileName ($($uniqueData.Count) entries)"
        $fileCount++
    }
}

Write-Host "`nTotal files created: $fileCount"
Write-Host "Output directory: $OutputDirectory"
