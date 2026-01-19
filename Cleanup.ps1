#Requires -RunAsAdministrator

function Clear-HibernateCache {
    # Check if Hibernate is enabled
    $hibernateStatus = (powercfg /availablesleepstates | Select-String "Hibernate") -ne $null

    if ($hibernateStatus) {
        Write-Host "Clearing Hibernate cache..."
        # Disable Hibernate (deletes hiberfil.sys)
        powercfg /hibernate off
        
        # Optional: Re-enable Hibernate if needed (remove comment to enable)
        # powercfg /hibernate on
        
        Write-Host "Hibernate cache cleared (hiberfil.sys removed)"
    } else {
        Write-Host "Hibernate is not enabled - nothing to clear"
    }
}

function Clear-StandbyMemory {
    Write-Host "Clearing Standby Memory (Sleep cache)..."
    
    # Use C# code to clear standby list
    Add-Type -TypeDefinition @"
    using System;
    using System.Runtime.InteropServices;
    public class Cleaner {
        [DllImport("kernel32.dll")]
        public static extern bool SetProcessWorkingSetSize(IntPtr handle, int minimumWorkingSetSize, int maximumWorkingSetSize);
    }
"@

    # Clear standby list using Windows API
    [Cleaner]::SetProcessWorkingSetSize(-1, -1, -1)
    Write-Host "Standby memory cleared"
}

function Clear-TempFiles {
    Write-Host "Clearing temporary files..."
    cleanmgr /sagerun:1 | Out-Null
    Remove-Item -Path "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -Path "C:\Windows\Temp\*" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Temporary files cleared"
}

# Execute all cleanup tasks
Clear-HibernateCache
Clear-StandbyMemory
Clear-TempFiles

Write-Host "`nAll cleanup operations completed!"