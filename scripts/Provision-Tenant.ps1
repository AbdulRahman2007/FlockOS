[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $ApiBaseUri,

    [Parameter(Mandatory = $true)]
    [ValidateLength(1, 160)]
    [string] $TenantName,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[^\s@]+@[^\s@]+\.[^\s@]+$')]
    [string] $OwnerEmail,

    [Parameter(Mandatory = $true)]
    [ValidateLength(1, 160)]
    [string] $OwnerName
)

$ErrorActionPreference = 'Stop'
$apiUri = [Uri] $ApiBaseUri.TrimEnd('/')
if ($apiUri.Scheme -ne 'https' -and $apiUri.Host -notin @('localhost', '127.0.0.1', '::1')) {
    throw 'Use HTTPS for tenant provisioning outside localhost.'
}
if (
    $apiUri.AbsolutePath.TrimEnd('/') -notmatch '/api/v1$' -or
    $apiUri.Query -or $apiUri.Fragment -or $apiUri.UserInfo
) {
    throw 'ApiBaseUri must end with /api/v1.'
}

$secureDirectory = Join-Path $env:LOCALAPPDATA 'POUKTRY\tenant-invites'
New-Item -ItemType Directory -Path $secureDirectory -Force | Out-Null
$currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
$directoryAcl = Get-Acl -LiteralPath $secureDirectory
$directoryAcl.SetAccessRuleProtection($true, $false)
$directoryAcl.SetOwner($currentSid)
foreach ($existingRule in @($directoryAcl.Access)) {
    $directoryAcl.RemoveAccessRuleAll($existingRule)
}
$privateRule = [System.Security.AccessControl.FileSystemAccessRule]::new(
    $currentSid,
    [System.Security.AccessControl.FileSystemRights]::FullControl,
    [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [System.Security.AccessControl.InheritanceFlags]::ObjectInherit,
    [System.Security.AccessControl.PropagationFlags]::None,
    [System.Security.AccessControl.AccessControlType]::Allow
)
$directoryAcl.AddAccessRule($privateRule)
Set-Acl -LiteralPath $secureDirectory -AclObject $directoryAcl

$bearerSecure = Read-Host 'Super Admin access token' -AsSecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($bearerSecure)
$bearer = $null
try {
    $bearer = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
    $headers = @{ Authorization = "Bearer $bearer" }
    $requestBody = @{
        tenant_name = $TenantName
        owner_email = $OwnerEmail
        owner_name = $OwnerName
    } | ConvertTo-Json -Compress

    $invite = Invoke-RestMethod -Method Post `
        -Uri "$($apiUri.AbsoluteUri.TrimEnd('/'))/auth/tenants" `
        -Headers $headers `
        -ContentType 'application/json' `
        -Body $requestBody

    $inviteFile = Join-Path $secureDirectory ("owner-invite-{0}.json" -f [Guid]::NewGuid().ToString('N'))
    $invite | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $inviteFile -Encoding utf8
    Write-Output "Tenant provisioned. Tenant ID: $($invite.tenant_id). Invitation ID: $($invite.invitation_id)"
    Write-Output "Owner invite token saved in the current-user-only file: $inviteFile"
    Write-Output 'Deliver that token to the owner through an approved secure channel, then remove the file after acceptance.'
}
catch {
    throw 'Tenant provisioning failed. Check the API status and retry only after confirming whether the tenant was created.'
}
finally {
    $bearer = $null
    $headers = $null
    $requestBody = $null
    if ($tokenPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
    }
    $bearerSecure.Dispose()
}
