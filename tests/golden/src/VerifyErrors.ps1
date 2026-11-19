$ErrorActionPreference='Stop'
foreach($case in @(@{name='empty arguments';args=''},@{name='missing PNG';args='--images C:\work\absent.png --output C:\work\deliverable\never-created.prn'})){
 $info=New-Object Diagnostics.ProcessStartInfo
 $info.FileName='C:\work\deliverable\PrintPng.exe'
 $info.Arguments=$case.args
 $info.UseShellExecute=$false
 $info.RedirectStandardError=$true
 $p=[Diagnostics.Process]::Start($info)
 $err=$p.StandardError.ReadToEnd()
 $p.WaitForExit()
 if($p.ExitCode -ne 1){throw "Expected exit 1: $($case.name)"}
 "Expected error ($($case.name)), exit $($p.ExitCode): $(($err -split "`r?`n")[0])"
 $p.Dispose()
}
