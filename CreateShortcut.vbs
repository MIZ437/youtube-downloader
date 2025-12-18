' Create Desktop Shortcut for YouTube Downloader
Option Explicit

Dim objShell, objShortcut, strDesktop, strPath, strTarget

Set objShell = CreateObject("WScript.Shell")

' Get paths
strDesktop = objShell.SpecialFolders("Desktop")
strPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
strTarget = strPath & "\YouTubeDownloader.vbs"

' Create shortcut
Set objShortcut = objShell.CreateShortcut(strDesktop & "\YouTube Downloader.lnk")
objShortcut.TargetPath = strTarget
objShortcut.WorkingDirectory = strPath
objShortcut.Description = "YouTube Downloader"
objShortcut.IconLocation = strPath & "\icon.ico,0"
objShortcut.Save

MsgBox "Desktop shortcut created!", vbInformation, "Complete"

Set objShortcut = Nothing
Set objShell = Nothing
