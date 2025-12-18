' YouTube Downloader 起動スクリプト
' コンソールを表示せずにランチャーを起動
' ダブルクリックで実行

Option Explicit

Dim objShell, objFSO, strPath, strPython, strLauncher, strCmd

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' 現在のスクリプトのディレクトリを取得
strPath = objFSO.GetParentFolderName(WScript.ScriptFullName)

' ランチャースクリプトのパス
strLauncher = strPath & "\launcher.pyw"

' Pythonのパスを探す
strPython = FindPython()

If strPython = "" Then
    MsgBox "Pythonが見つかりません。" & vbCrLf & vbCrLf & _
           "Python 3.9以上をインストールしてください。" & vbCrLf & _
           "https://www.python.org/downloads/", vbCritical, "エラー"
    WScript.Quit 1
End If

' ランチャーが存在するか確認
If Not objFSO.FileExists(strLauncher) Then
    MsgBox "launcher.pyw が見つかりません。" & vbCrLf & _
           "ファイルが正しく配置されているか確認してください。", vbCritical, "エラー"
    WScript.Quit 1
End If

' pythonw.exe を使ってコンソール非表示で起動
strCmd = """" & strPython & """ """ & strLauncher & """"
objShell.Run strCmd, 0, False

' クリーンアップ
Set objShell = Nothing
Set objFSO = Nothing

' Pythonを探す関数
Function FindPython()
    Dim arrPaths, strTestPath, i

    FindPython = ""

    ' よくあるPythonのインストール場所
    arrPaths = Array( _
        objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\pythonw.exe", _
        objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python311\pythonw.exe", _
        objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python310\pythonw.exe", _
        objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python39\pythonw.exe", _
        "C:\Python312\pythonw.exe", _
        "C:\Python311\pythonw.exe", _
        "C:\Python310\pythonw.exe", _
        "C:\Python39\pythonw.exe", _
        objShell.ExpandEnvironmentStrings("%PROGRAMFILES%") & "\Python312\pythonw.exe", _
        objShell.ExpandEnvironmentStrings("%PROGRAMFILES%") & "\Python311\pythonw.exe" _
    )

    ' 各パスをチェック
    For i = 0 To UBound(arrPaths)
        If objFSO.FileExists(arrPaths(i)) Then
            FindPython = arrPaths(i)
            Exit Function
        End If
    Next

    ' PATHからpythonw.exeを探す
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
