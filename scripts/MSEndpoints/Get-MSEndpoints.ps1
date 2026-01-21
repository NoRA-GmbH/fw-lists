#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Fetches Microsoft 365 endpoints and creates firewall list files.

.DESCRIPTION
    This script fetches Microsoft 365 endpoints from the official Microsoft API
    and generates list files that can be used in firewall configurations.
    
    Two types of files are generated:
    
    1. Category-based files (always generated): ms365_{{serviceArea}}_{{addrType}}_{{category}}.txt
       where:
       - serviceArea: common, exchange, sharepoint, teams, etc.
       - addrType: url, ipv4, ipv6
       - category: opt, allow, default
    
    2. Port-based files (optional, only when GeneratePortListsFor is specified): ms365_{{serviceArea}}_{{addrType}}_port{{port}}.txt
       where:
       - serviceArea: common, exchange, sharepoint, teams, etc.
       - addrType: url, ipv4, ipv6
       - port: specific port number (e.g., 25, 80, 443)
       
       These files contain only the IPs or URLs that use the specified port,
       making it easier to configure port-specific firewall rules.
       By default, no port-specific files are generated.

.PARAMETER OutputDirectory
    Directory where the list files will be saved. Default is '../../lists/ms365'

.PARAMETER ClientRequestId
    Optional client request ID for API tracking. A random GUID is generated if not provided.

.PARAMETER GeneratePortListsFor
    Optional array of port-specific lists to generate in addition to category-based lists.
    Format: "servicearea:addrtype:port" or "servicearea:addrtype:port1-port2-port3"
    Examples: @("exchange:ipv4:25", "exchange:url:80-443", "teams:url:443")
    If not specified, only category-based lists are generated.

.EXAMPLE
    .\Get-MSEndpoints.ps1
    .\Get-MSEndpoints.ps1 -OutputDirectory "./output"
    .\Get-MSEndpoints.ps1 -GeneratePortListsFor @("exchange:ipv4:25", "teams:url:80-443")
#>

param(
    [Parameter(Mandatory = $false)]
    [string]$OutputDirectory = "../../lists/ms365",
    
    [Parameter(Mandatory = $false)]
    [string]$ClientRequestId = [guid]::NewGuid().ToString(),
    
    [Parameter(Mandatory = $false)]
    [string[]]$GeneratePortListsFor = @()
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Default configuration: Define which service areas and address types should generate port-specific files
# Format: ServiceArea -> AddressType -> Array of Ports
# Only the specified combinations will generate port-specific files
# This is used when -GeneratePortListsFor parameter is not provided
# Note: Service areas are: common, exchange, sharepoint, skype (Teams is called "Skype" in the API)
# By default, no port-specific lists are generated (empty configuration)
$ServicePortMap = @{}

# Parse GeneratePortListsFor parameter if provided
if ($GeneratePortListsFor.Count -gt 0) {
    Write-Host "Using custom port list configuration from parameter"
    $ServicePortMap = @{}
    
    foreach ($spec in $GeneratePortListsFor) {
        $parts = $spec -split ':'
        if ($parts.Count -ne 3) {
            Write-Warning "Invalid format for '$spec'. Expected format: 'servicearea:addrtype:port' or 'servicearea:addrtype:port1-port2'"
            continue
        }
        
        $serviceArea = $parts[0].ToLower()
        $addrType = $parts[1].ToLower()
        $portSpec = $parts[2]
        
        # Parse ports (can be single port or hyphen-separated list)
        $ports = if ($portSpec -match '-') {
            ($portSpec -split '-') | ForEach-Object { [int]$_ }
        } else {
            @([int]$portSpec)
        }
        
        # Initialize nested hashtable if needed
        if (-not $ServicePortMap.ContainsKey($serviceArea)) {
            $ServicePortMap[$serviceArea] = @{}
        }
        if (-not $ServicePortMap[$serviceArea].ContainsKey($addrType)) {
            $ServicePortMap[$serviceArea][$addrType] = @()
        }
        
        # Add ports to configuration
        $ServicePortMap[$serviceArea][$addrType] += $ports
    }
}

# Helper function to check if port-specific file should be generated
function Should-GeneratePortFile {
    param(
        [string]$ServiceArea,
        [string]$AddrType,
        [int]$Port
    )
    
    if ($ServicePortMap.ContainsKey($ServiceArea)) {
        if ($ServicePortMap[$ServiceArea].ContainsKey($AddrType)) {
            return $ServicePortMap[$ServiceArea][$AddrType] -contains $Port
        }
    }
    return $false
}

# Create output directory if it doesn't exist
if (-not (Test-Path -Path $OutputDirectory)) {
    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
    Write-Host "Created output directory: $OutputDirectory"
}

# Clean up output directory - remove all existing files before generating new ones
if (Test-Path -Path $OutputDirectory) {
    $existingFiles = Get-ChildItem -Path $OutputDirectory -Filter "*.txt"
    
    if ($existingFiles.Count -gt 0) {
        Write-Host "Removing $($existingFiles.Count) existing file(s) from output directory..."
        $existingFiles | Remove-Item -Force
    }
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

# Initialize hashtables to group data
$groupedData = @{}
$groupedDataByPort = @{}

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
    
    # Get port information for port-specific lists
    $tcpPorts = if ($endpoint.tcpPorts) { 
        # Parse ports into array (remove spaces, split by comma)
        ($endpoint.tcpPorts -replace '\s+', '' -split ',') | ForEach-Object { [int]$_ }
    } else { 
        @() 
    }
    
    # Process URLs
    if ($endpoint.urls) {
        $key = "${serviceArea}_url_${category}"
        if (-not $groupedData.ContainsKey($key)) {
            $groupedData[$key] = @()
        }
        foreach ($url in $endpoint.urls) {
            if ($url -and $url.Trim() -ne "") {
                $groupedData[$key] += $url
                
                # Also add to port-specific lists if configured
                foreach ($port in $tcpPorts) {
                    if (Should-GeneratePortFile -ServiceArea $serviceArea -AddrType "url" -Port $port) {
                        $portKey = "${serviceArea}_url_port${port}"
                        if (-not $groupedDataByPort.ContainsKey($portKey)) {
                            $groupedDataByPort[$portKey] = @()
                        }
                        $groupedDataByPort[$portKey] += $url
                    }
                }
            }
        }
    }
    
    # Process IPv4 addresses
    if ($endpoint.ips) {
        foreach ($ip in $endpoint.ips) {
            # Check if it's IPv4 (contains dots but not colons)
            if ($ip -match '^\d+\.\d+\.\d+\.\d+' -and $ip -notmatch ':') {
                $key = "${serviceArea}_ipv4_${category}"
                if (-not $groupedData.ContainsKey($key)) {
                    $groupedData[$key] = @()
                }
                if ($ip -and $ip.Trim() -ne "") {
                    $groupedData[$key] += $ip
                    
                    # Also add to port-specific lists if configured
                    foreach ($port in $tcpPorts) {
                        if (Should-GeneratePortFile -ServiceArea $serviceArea -AddrType "ipv4" -Port $port) {
                            $portKey = "${serviceArea}_ipv4_port${port}"
                            if (-not $groupedDataByPort.ContainsKey($portKey)) {
                                $groupedDataByPort[$portKey] = @()
                            }
                            $groupedDataByPort[$portKey] += $ip
                        }
                    }
                }
            }
            # Check if it's IPv6 (contains colons)
            elseif ($ip -match ':') {
                $key = "${serviceArea}_ipv6_${category}"
                if (-not $groupedData.ContainsKey($key)) {
                    $groupedData[$key] = @()
                }
                if ($ip -and $ip.Trim() -ne "") {
                    $groupedData[$key] += $ip
                    
                    # Also add to port-specific lists if configured
                    foreach ($port in $tcpPorts) {
                        if (Should-GeneratePortFile -ServiceArea $serviceArea -AddrType "ipv6" -Port $port) {
                            $portKey = "${serviceArea}_ipv6_port${port}"
                            if (-not $groupedDataByPort.ContainsKey($portKey)) {
                                $groupedDataByPort[$portKey] = @()
                            }
                            $groupedDataByPort[$portKey] += $ip
                        }
                    }
                }
            }
        }
    }
}

# Write data to files (original format by category)
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

# Write data to files (port-specific format)
foreach ($key in $groupedDataByPort.Keys | Sort-Object) {
    # Remove duplicates and sort
    $uniqueData = $groupedDataByPort[$key] | Select-Object -Unique | Sort-Object
    
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
