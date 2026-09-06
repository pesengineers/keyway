<#
.SYNOPSIS
    Create (or reuse) the Entra ID app registration that lets Keyway download
    SharePoint files through Microsoft Graph with client credentials.

.DESCRIPTION
    Idempotent. Run it as a Global Administrator or Application Administrator
    who can also grant admin consent. It will:

      1. Find or create an application named -DisplayName.
      2. Ensure a service principal exists for it.
      3. Add the requested Microsoft Graph *application* permission and grant
         admin consent (app role assignment), so no portal click is needed.
         Default: Sites.Selected, then grant "read" on the one SharePoint site
         passed in -SiteId (least privilege). Use -TenantWide for Files.Read.All.
      4. Create a client secret (only when none exists, or when -RotateSecret).
         The secret is written to -SecretOutFile with owner-only ACL and is
         never echoed to the console.
      5. Print the GRAPH_* environment block (minus the secret) for the Keyway
         container.

    Re-running without -RotateSecret changes nothing and reprints the IDs.

.PARAMETER SiteId
    Graph site id, e.g. "pes1852.sharepoint.com,97c4bdef-...,316269b2-...".
    Required unless -TenantWide.

.EXAMPLE
    .\scripts\New-KeywayGraphApp.ps1 -SiteId "pes1852.sharepoint.com,97c4bdef-10db-4a0a-b359-050ced66dd51,316269b2-8c0d-438a-9466-a3a1f9800a8a"

.EXAMPLE
    .\scripts\New-KeywayGraphApp.ps1 -TenantWide -RotateSecret

.NOTES
    Requires: Install-Module Microsoft.Graph -Scope CurrentUser
    Delegated scopes requested at sign-in:
      Application.ReadWrite.All, AppRoleAssignment.ReadWrite.All,
      Directory.Read.All, and Sites.FullControl.All (only for the site grant).
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string] $DisplayName = "Keyway Video Worker",
    [string] $SiteId,
    [switch] $TenantWide,
    [switch] $RotateSecret,
    [int]    $SecretValidDays = 365,
    [string] $SecretOutFile = (Join-Path $env:USERPROFILE ".keyway\graph-client-secret.txt")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $TenantWide -and -not $SiteId) {
    throw "Provide -SiteId for a least-privilege Sites.Selected grant, or -TenantWide for Files.Read.All."
}

# Microsoft Graph service principal app id is constant across tenants.
$GraphAppId = "00000003-0000-0000-c000-000000000000"
$PermissionName = if ($TenantWide) { "Files.Read.All" } else { "Sites.Selected" }

# ---------------------------------------------------------------- sign in ---
$scopes = @("Application.ReadWrite.All", "AppRoleAssignment.ReadWrite.All", "Directory.Read.All")
if (-not $TenantWide) { $scopes += "Sites.FullControl.All" }

Import-Module Microsoft.Graph.Applications -ErrorAction Stop
Import-Module Microsoft.Graph.Authentication -ErrorAction Stop
Connect-MgGraph -Scopes $scopes -NoWelcome
$ctx = Get-MgContext
Write-Host "Signed in to tenant $($ctx.TenantId) as $($ctx.Account)"

# ----------------------------------------------------- application object ---
$app = Get-MgApplication -Filter "displayName eq '$DisplayName'" -ConsistencyLevel eventual -CountVariable c | Select-Object -First 1
if (-not $app) {
    if ($PSCmdlet.ShouldProcess($DisplayName, "Create application registration")) {
        $app = New-MgApplication -DisplayName $DisplayName -SignInAudience "AzureADMyOrg" -Notes "Keyway worker: read-only SharePoint file access via Graph. Managed by scripts/New-KeywayGraphApp.ps1 in pesengineers/keyway."
        Write-Host "Created application $($app.AppId)"
    }
} else {
    Write-Host "Reusing existing application $($app.AppId)"
}

# ------------------------------------------------------ service principal ---
$sp = Get-MgServicePrincipal -Filter "appId eq '$($app.AppId)'" | Select-Object -First 1
if (-not $sp) {
    if ($PSCmdlet.ShouldProcess($DisplayName, "Create service principal")) {
        $sp = New-MgServicePrincipal -AppId $app.AppId
        Write-Host "Created service principal $($sp.Id)"
    }
} else {
    Write-Host "Reusing service principal $($sp.Id)"
}

# ------------------------------------------- required resource access (UI) ---
$graphSp = Get-MgServicePrincipal -Filter "appId eq '$GraphAppId'" | Select-Object -First 1
$role = $graphSp.AppRoles | Where-Object { $_.Value -eq $PermissionName -and $_.AllowedMemberTypes -contains "Application" }
if (-not $role) { throw "Graph app role '$PermissionName' not found." }

$existingAccess = @($app.RequiredResourceAccess | Where-Object { $_.ResourceAppId -eq $GraphAppId })
$hasRole = $existingAccess | ForEach-Object { $_.ResourceAccess } | Where-Object { $_.Id -eq $role.Id -and $_.Type -eq "Role" }
if (-not $hasRole) {
    if ($PSCmdlet.ShouldProcess($DisplayName, "Declare Graph permission $PermissionName")) {
        $access = @{
            ResourceAppId  = $GraphAppId
            ResourceAccess = @(@{ Id = $role.Id; Type = "Role" })
        }
        Update-MgApplication -ApplicationId $app.Id -RequiredResourceAccess @($access)
        Write-Host "Declared $PermissionName on the application"
    }
} else {
    Write-Host "$PermissionName already declared"
}

# ---------------------------------------------- admin consent (role grant) ---
$assigned = Get-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $sp.Id | Where-Object { $_.AppRoleId -eq $role.Id -and $_.ResourceId -eq $graphSp.Id }
if (-not $assigned) {
    if ($PSCmdlet.ShouldProcess($DisplayName, "Grant admin consent for $PermissionName")) {
        New-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $sp.Id -PrincipalId $sp.Id -ResourceId $graphSp.Id -AppRoleId $role.Id | Out-Null
        Write-Host "Admin consent granted for $PermissionName"
    }
} else {
    Write-Host "Admin consent already granted for $PermissionName"
}

# ------------------------------------------- per-site grant (Sites.Selected) ---
if (-not $TenantWide) {
    $perms = Invoke-MgGraphRequest -Method GET -Uri "https://graph.microsoft.com/v1.0/sites/$SiteId/permissions"
    $already = $perms.value | Where-Object {
        $_.grantedToIdentitiesV2 | ForEach-Object { $_.application.id } | Where-Object { $_ -eq $app.AppId }
    }
    if (-not $already) {
        if ($PSCmdlet.ShouldProcess($SiteId, "Grant site permission 'read' to $DisplayName")) {
            $body = @{
                roles               = @("read")
                grantedToIdentities = @(@{ application = @{ id = $app.AppId; displayName = $DisplayName } })
            }
            Invoke-MgGraphRequest -Method POST -Uri "https://graph.microsoft.com/v1.0/sites/$SiteId/permissions" -Body $body | Out-Null
            Write-Host "Granted 'read' on site $SiteId"
        }
    } else {
        Write-Host "Site 'read' permission already present"
    }
}

# ------------------------------------------------------------- client secret ---
$app = Get-MgApplication -ApplicationId $app.Id
$liveSecrets = @($app.PasswordCredentials | Where-Object { $_.EndDateTime -gt (Get-Date) })
$needSecret = $RotateSecret -or ($liveSecrets.Count -eq 0)
if ($needSecret) {
    if ($PSCmdlet.ShouldProcess($DisplayName, "Create client secret valid $SecretValidDays days")) {
        $cred = @{
            DisplayName = "keyway-$(Get-Date -Format yyyyMMdd)"
            EndDateTime = (Get-Date).AddDays($SecretValidDays)
        }
        $pw = Add-MgApplicationPassword -ApplicationId $app.Id -PasswordCredential $cred

        $dir = Split-Path $SecretOutFile -Parent
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        [System.IO.File]::WriteAllText($SecretOutFile, $pw.SecretText, [System.Text.Encoding]::ASCII)
        icacls $SecretOutFile /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null
        Write-Host "Client secret written to $SecretOutFile (expires $($cred.EndDateTime.ToString('yyyy-MM-dd')))."
        Write-Host "Store it in 1Password now, then delete the file. It cannot be retrieved again."
    }
} else {
    $exp = ($liveSecrets | Sort-Object EndDateTime | Select-Object -Last 1).EndDateTime
    Write-Host "A client secret already exists (expires $($exp.ToString('yyyy-MM-dd'))). Use -RotateSecret to add a new one."
}

# ----------------------------------------------------------------- output ---
Write-Host ""
Write-Host "Keyway container environment (secret intentionally omitted):"
Write-Host "GRAPH_TENANT_ID=$($ctx.TenantId)"
Write-Host "GRAPH_CLIENT_ID=$($app.AppId)"
Write-Host "GRAPH_CLIENT_SECRET=<from $SecretOutFile or 1Password>"
Write-Host "GRAPH_BASE_URL=https://graph.microsoft.com/v1.0"
Write-Host ""
Write-Host "Permission model: $PermissionName$(if (-not $TenantWide) { " with 'read' on $SiteId" })"

Disconnect-MgGraph | Out-Null
