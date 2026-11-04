[CmdletBinding()]
param([string]$AdbPath, [string]$Serial, [switch]$CheckOnly)
$ErrorActionPreference='Stop'
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
$cache=Join-Path $PSScriptRoot '.installer-cache'
function FileHash([string]$Path) {
 $stream=[IO.File]::OpenRead($Path)
 $sha=[Security.Cryptography.SHA256]::Create()
 try {return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','')}
 finally {$stream.Dispose();$sha.Dispose()}
}
function Download([string]$Url,[string]$Path,[string]$Sha) {
 if(!(Test-Path -LiteralPath $Path) -or ($Sha -and (FileHash $Path) -ne $Sha)) {
  Write-Host "Downloading $(Split-Path $Path -Leaf)..."
  Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile "$Path.part"
  if($Sha -and (FileHash "$Path.part") -ne $Sha){throw "Checksum mismatch: $Url"}
  Move-Item -LiteralPath "$Path.part" -Destination $Path -Force
 }
 return $Path
}
function Adb([string[]]$Arguments) {
 $output=& $script:AdbPath @Arguments 2>&1
 if($LASTEXITCODE -ne 0){throw "ADB failed: $($output -join [Environment]::NewLine)"}
 return $output
}
function Device([string[]]$Arguments) { Adb (@('-s',$script:Serial)+$Arguments) }
function Root([string]$Command) {
 # Commands are fixed installer paths; never interpolate arbitrary user text.
 Device @('shell',"run-as com.termux $script:Su -mm -c '$Command'")
}
try {
 if(!$AdbPath) {
  $found=Get-Command adb -ErrorAction SilentlyContinue
  if($found){$AdbPath=$found.Source}
  elseif(Test-Path "$PSScriptRoot/platform-tools/adb.exe"){$AdbPath="$PSScriptRoot/platform-tools/adb.exe"}
  elseif($CheckOnly){throw 'ADB required. Supply -AdbPath or put platform-tools beside this script.'}
  else {
   New-Item -ItemType Directory -Force $cache | Out-Null
   # Google serves platform-tools-latest over HTTPS; unlike pinned runtime assets this tracks upstream.
   $zip=Download 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip' "$cache/platform-tools.zip" ''
   Expand-Archive -LiteralPath $zip -DestinationPath $cache -Force
   $AdbPath="$cache/platform-tools/adb.exe"
  }
 }
 $AdbPath=(Resolve-Path -LiteralPath $AdbPath).Path
 $devices=@(Adb @('devices') | Where-Object {$_ -match '^([^\s]+)\s+device$'} | ForEach-Object {($_ -split '\s+')[0]})
 if(!$Serial) {
  if($devices.Count -ne 1){throw 'Connect exactly one authorized Echo, or supply -Serial. Enable USB debugging and approve this computer.'}
  $Serial=$devices[0]
 }
 if($Serial -notin $devices){throw 'Selected device is not connected and authorized.'}
 if(($Serial -notmatch '^[A-Za-z0-9._:-]+$')){throw 'Invalid serial'}
 $model=(Device @('shell','getprop ro.product.device') | Out-String).Trim()
 $sdk=(Device @('shell','getprop ro.build.version.sdk') | Out-String).Trim()
 $abi=(Device @('shell','getprop ro.product.cpu.abi') | Out-String).Trim()
 if($model -ne 'cronos' -or $sdk -ne '30' -or $abi -ne 'armeabi-v7a'){throw "Only Echo Show 5 Gen 2 (cronos), Android 11 / ARMv7 is supported. Found $model / SDK $sdk / $abi"}
 $termux=(Device @('shell','pm path com.termux') | Out-String).Trim()
 if(!$termux) {
  if($CheckOnly){throw 'Termux is missing; normal install will download and install it.'}
  New-Item -ItemType Directory -Force $cache | Out-Null
  $asset=Get-Content "$PSScriptRoot/installer/downloads.json" -Raw | ConvertFrom-Json | Where-Object {$_.file -eq 'termux.apk'}
  $apk=Download $asset.url "$cache/termux.apk" $asset.sha256
  Device @('install',$apk) | Write-Host
  Device @('shell','am start -n com.termux/.app.TermuxActivity') | Write-Host
  Write-Host 'Waiting for first-run Termux initialization on the Echo...'
  $ready=$false
  for($i=0;$i -lt 60;$i++) {
   $probe=Device @('shell','run-as com.termux sh -c "if test -x files/usr/bin/bash; then echo ready; fi"')
   if(($probe -join '') -match 'ready'){$ready=$true;break}
   Start-Sleep -Seconds 2
  }
  if(!$ready){throw 'Open Termux on the Echo, let initialization finish, then rerun.'}
 }
 $Su=(Device @('shell','command -v su') | Out-String).Trim()
 if($Su -notmatch '^/(system/(xbin|bin)/su|sbin/su)$'){throw 'Supported Magisk su not found. Install/configure Magisk first.'}
 Write-Host 'Checking root. Approve Termux in Magisk on the Echo if prompted.'
 $identity=Root 'id'
 if(($identity -join '') -notmatch 'uid=0'){throw 'Root was not granted to Termux.'}
 $mode=(Root 'if test -f /data/local/echo-airplay/.touch-installer-incomplete; then echo fresh; elif test -x /data/local/echo-airplay/usr/local/bin/shairport-sync; then echo upgrade; elif test -e /data/local/echo-airplay; then echo unknown; else echo fresh; fi' | Out-String).Trim()
 if($mode -notin @('fresh','upgrade')){throw 'An unknown runtime directory already exists; refusing to overwrite it.'}
 $apk="$PSScriptRoot/dist/Echo-AirPlay.apk"
 $apkHash=((Get-Content "$apk.sha256" -Raw) -split '\s+')[0]
 if((FileHash $apk) -ne $apkHash){throw 'Bundled touch APK checksum mismatch.'}
 Write-Host "PASS: cronos, Android 11, ARMv7, authorized ADB, Termux root, verified touch APK. Mode: $mode"
 if($CheckOnly){Write-Host 'Check complete. No device files changed.';exit 0}
 New-Item -ItemType Directory -Force $cache | Out-Null
 $stage='/data/local/tmp/echo-touch-installer'
 Device @('shell',"mkdir -p $stage") | Out-Null
 $files=@('preferences.py','local_audio.py','pairing.py','reliability.py','receiver.py','server.py','index.html','install.sh','start-touch.sh','echo-boot.sh') | ForEach-Object {Join-Path $PSScriptRoot $_}
 $files+=@(Get-ChildItem "$PSScriptRoot/installer/*.sh" | ForEach-Object {$_.FullName})
 foreach($file in $files){Device @('push',$file,"$stage/") | Write-Host}
 if($mode -eq 'fresh') {
  $free=(Root 'df -Pk /data' | Select-Object -Last 1) -split '\s+'
  if([long]$free[3] -lt 1500000){throw 'Fresh installation needs at least 1.5 GB free in /data.'}
  $assets=Get-Content "$PSScriptRoot/installer/downloads.json" -Raw | ConvertFrom-Json
  foreach($asset in $assets | Where-Object {$_.file -ne 'termux.apk'}) {
   $path=Download $asset.url (Join-Path $cache $asset.file) $asset.sha256
   Device @('push',$path,"$stage/") | Write-Host
  }
  Device @('shell',"run-as com.termux /system/bin/sh $stage/termux-packages.sh") | Write-Host
 }
 # Fail early on a signing-key conflict without deleting an existing app or its settings.
 Device @('install','-r',$apk) | Write-Host
 Write-Host 'Installing. Fresh source builds can take tens of minutes; keep power and USB connected.'
 & $AdbPath -s $Serial shell "run-as com.termux $Su -mm -c '/system/bin/sh $stage/deploy-device.sh $mode'"
 if($LASTEXITCODE -ne 0){throw "Device installation failed; see the build output above."}
 Device @('shell','am force-stop io.blue1ms.echoairplay') | Out-Null
 Device @('shell','am start -n io.blue1ms.echoairplay/.MainActivity') | Write-Host
 Write-Host 'Done. Select this receiver in AirPlay. No second Echo or running PC is required.'
 Write-Host 'HA and MA are optional. Leave Connections unconfigured for pure AirPlay.'
 Write-Host 'For home controls, tap Setup and enter your own reachable Home Assistant URL; sign in on the Echo.'
} catch {
 Write-Error -ErrorAction Continue $_
 Write-Host 'Installation stopped. No ROM was flashed. Resolve the error and rerun; existing pairing is preserved.'
 exit 1
}
