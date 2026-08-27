Option Explicit

Dim shell, fso, projectDir, startScript, command

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
startScript = fso.BuildPath(projectDir, "tools\start_youffice.ps1")

If Not fso.FileExists(startScript) Then
    MsgBox "YOUFFICE start script not found:" & vbCrLf & startScript, vbCritical, "YOUFFICE"
    WScript.Quit 1
End If

command = "powershell.exe -NoLogo -ExecutionPolicy Bypass -File " & Chr(34) & startScript & Chr(34)
shell.Run command, 1, False
