$ErrorActionPreference='Stop'
& "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /out:C:\work\deliverable\PrintPng.exe /r:System.Drawing.dll /r:System.Web.Extensions.dll /r:C:\Windows\Microsoft.NET\Framework64\v4.0.30319\WPF\System.Printing.dll /r:C:\Windows\Microsoft.NET\Framework64\v4.0.30319\WPF\ReachFramework.dll C:\work\deliverable\src\PrintPng.cs
if($LASTEXITCODE -ne 0){throw 'Compilation failed'}
