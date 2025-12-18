' YouTube Downloader Launcher
' Launches the app without console window
Option Explicit

Dim objShell, objFSO, strPath, strPython, strLauncher, strCmd

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

strPath = objFSO.GetParentFolderName(WScript.ScriptFullName)
strLauncher = strPath & "\launcher.pyw"
strPython = FindPython()

If strPython = "" Then
    MsgBox "Python not found." & vbCrLf & vbCrLf & "Please install Python 3.9 or later:" & vbCrLf & "https://www.python.org/downloads/", vbCritical, "Error"
    WScript.Quit 1
End If

If Not objFSO.FileExists(strLauncher) Then
    MsgBox "launcher.pyw not found." & vbCrLf & "Please check the file location.", vbCritical, "Error"
    WScript.Quit 1
End If

strCmd = """" & strPython & """ """ & strLauncher & """"
objShell.Run strCmd, 0, False

Set objShell = Nothing
Set objFSO = Nothing

Function FindPython()
    Dim arrPaths, strTestPath, i
    FindPython = ""

    arrPaths = Array( _
        objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python313\pythonw.exe", _
        objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\pythonw.exe", _
        objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python311\pythonw.exe", _
        objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python310\pythonw.exe", _
        objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python39\pythonw.exe", _
        "C:\Python313\pythonw.exe", _
        "C:\Python312\pythonw.exe", _
        "C:\Python311\pythonw.exe", _
        "C:\Python310\pythonw.exe", _
        "C:\Python39\pythonw.exe", _
        objShell.ExpandEnvironmentStrings("%PROGRAMFILES%") & "\Python312\pythonw.exe", _
        objShell.ExpandEnvironmentStrings("%PROGRAMFILES%") & "\Python311\pythonw.exe" _
    )

    For i = 0 To UBound(arrPaths)
        If objFSO.FileExists(arrPaths(i)) Then
            FindPython = arrPaths(i)
            Exit Function
        End If
    Next

    On Error Resume Next
    strTestPath = objShell.ExpandEnvironmentStrings("%PATH%")
    Dim arrPathDirs, strDir
    arrPathDirs = Split(strTestPath, ";")
    For Each strDir In arrPathDirs
        strTestPath = strDir & "\pythonw.exe"
        If objFSO.FileExists(strTestPath) Then
            FindPython = strTestPath
            Exit Function
        End If
    Next
    On Error GoTo 0
End Function
