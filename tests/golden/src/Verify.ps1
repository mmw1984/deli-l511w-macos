$ErrorActionPreference='Stop'
$root='C:\work\deliverable'
$m=Get-Content "$root\manifest.json" -Raw | ConvertFrom-Json
$enc=[Text.Encoding]::GetEncoding(28591)
foreach($j in $m.jobs){
 $b=[IO.File]::ReadAllBytes($j.filename)
 $sha=[Security.Cryptography.SHA256]::Create()
 $hash=[BitConverter]::ToString($sha.ComputeHash($b)).Replace('-','')
 if($b.Length -ne $j.fileSize -or $hash -ne $j.sha256){throw "Size/hash mismatch: $($j.filename)"}
 if($j.devcaps.LOGPIXELSX -ne 600 -or $j.devcaps.LOGPIXELSY -ne 600){throw 'DPI mismatch'}
 [xml]$ticket=Get-Content $j.ticketFile -Raw
 $normalized=[regex]::Replace($enc.GetString($b),'(?m)^@PJL SET (JOBNAME|FPRINTFILEID|FDATETIME)=[^\r\n]*\r?\n','')
 $nh=[BitConverter]::ToString($sha.ComputeHash($enc.GetBytes($normalized))).Replace('-','')
 $j | Add-Member normalizedSha256 $nh -Force
 $header=$enc.GetString($b,0,[Math]::Min(1000,$b.Length))
 $quality=[regex]::Match($header,'PRINTQUALITY=([^\r\n]+)').Groups[1].Value
 $j | Add-Member pjlPrintQuality $quality -Force
 $sha.Dispose()
}
$groups=@($m.jobs | Group-Object normalizedSha256 | Where-Object Count -gt 1 | ForEach-Object {@{sha256=$_.Name;files=@($_.Group.filename)}})
$m | Add-Member identicalNormalizedOutputs $groups -Force
$m | ConvertTo-Json -Depth 30 | Set-Content "$root\manifest.json" -Encoding UTF8
"Verified $($m.jobs.Count) nonempty PRNs, SHA256s, 600x600 caps and parseable tickets."
"Identical normalized output groups (job name, print-file ID, timestamp removed): $($groups.Count)"
foreach($g in $groups){($g.files | ForEach-Object {[IO.Path]::GetFileName($_)}) -join ', '}
$m.jobs | Where-Object {$_.filename -match 'quality-|color_a4_media-light.prn'} | ForEach-Object {"$([IO.Path]::GetFileName($_.filename)): PRINTQUALITY=$($_.pjlPrintQuality)"}
