$ErrorActionPreference='Stop'
$root='C:\work\deliverable'
$images=@{
 color='C:\work\deliverable\inputs\a4_color_600.png'
 gray='C:\work\deliverable\inputs\a4_gray_600.png'
 band='C:\work\deliverable\inputs\a4_band_600.png'
}
function Job($name,$source,$color='color',$media='LIGHT',$paper='A4',$quality='standard-applied') {
 if(Test-Path "$root\$name.json"){return}
 & "$root\PrintPng.exe" --images $source --output "$root\prn\$name.prn" --color $color --media $media --paper $paper --devmode "$root\devmodes\$quality.bin" --ticket "$root\tickets\$name.xml" --record "$root\$name.json" --job $name
 if($LASTEXITCODE -ne 0){throw "Job $name failed"}
}
foreach($image in 'color','gray','band'){
 Job "${image}_a4_media-light" $images[$image]
 Job "${image}_mono_a4_media-light" $images[$image] 'mono'
}
foreach($media in 'MATTE','HEAVY','ENV','POSTCARD'){Job ('color_a4_media-'+$media.ToLower()) $images.color 'color' $media}
foreach($quality in 'draft','best'){Job "color_a4_media-light_quality-$quality" $images.color 'color' 'LIGHT' 'A4' $quality}
foreach($paper in 'Letter','A5','LetterCustom'){Job ('color_'+$paper.ToLower()+'_media-light') $images.color 'color' 'LIGHT' $paper}
Job 'color-gray_2page_a4_media-light' ($images.color+';'+$images.gray)
$jobs=@(Get-ChildItem $root -Filter '*.json' | Where-Object {$_.Name -ne 'manifest.json'} | ForEach-Object {Get-Content $_.FullName -Raw | ConvertFrom-Json} | Where-Object {$_.sha256})
$duplicates=@($jobs | Group-Object sha256 | Where-Object Count -gt 1 | ForEach-Object {@{sha256=$_.Name;files=@($_.Group.filename)}})
@{jobs=$jobs;identicalOutputs=$duplicates;notes=@('1 image pixel = 1 device pixel; physical page origin; printable clipping allowed.','PRN is a reserved Windows name; directory created with extended-length path.','Raw hashes include descriptive job names; different hashes alone do not prove raster differences.')} | ConvertTo-Json -Depth 30 | Set-Content "$root\manifest.json" -Encoding UTF8
$jobs | Sort-Object filename | Select-Object @{n='File';e={[IO.Path]::GetFileName($_.filename)}},fileSize,@{n='Paper';e={$_.devmode.dmPaperSize}},@{n='Physical';e={"$($_.devcaps.PHYSICALWIDTH)x$($_.devcaps.PHYSICALHEIGHT)"}} | Format-Table -AutoSize
"Jobs: $($jobs.Count); identical raw output groups: $($duplicates.Count)"
