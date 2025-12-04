###############################################################################
# Browse for .env file
# Returns the selected file path to stdout
###############################################################################

Add-Type -AssemblyName System.Windows.Forms

$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Filter = "Environment Files (*.env)|*.env|All Files (*.*)|*.*"
$dialog.Title = "Select .env Configuration File"
$dialog.InitialDirectory = [Environment]::GetFolderPath('MyDocuments')
$dialog.CheckFileExists = $true
$dialog.CheckPathExists = $true
$dialog.Multiselect = $false

if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $dialog.FileName
    exit 0
} else {
    exit 1
}
