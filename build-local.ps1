param([Parameter(Mandatory=$true)][string]$ToolchainDirectory)
$ErrorActionPreference='Stop'
$base=(Resolve-Path $ToolchainDirectory).Path
$src=Join-Path $PSScriptRoot android
$jdk=(Get-ChildItem "$base/jdk" -Directory | Select-Object -First 1).FullName
$env:JAVA_HOME=$jdk
$env:PATH="$jdk/bin;"+$env:PATH
$bt="$base/tools/android-11"
$platform="$base/platform/android-11/android.jar"
$build="$base/app"
New-Item -ItemType Directory -Force "$build/classes","$build/generated","$build/dex" | Out-Null
& "$bt/aapt.exe" package -f -m -M "$src/AndroidManifest.xml" -S "$src/res" -A "$src/assets" -I $platform -J "$build/generated" -F "$build/base.apk"
if($LASTEXITCODE){throw 'aapt failed'}
& "$jdk/bin/javac.exe" -encoding UTF-8 -source 8 -target 8 -classpath $platform -d "$build/classes" "$src/MainActivity.java" "$src/HomePanel.java" "$build/generated/io/blue1ms/echoairplay/R.java"
if($LASTEXITCODE){throw 'javac failed'}
& "$jdk/bin/jar.exe" cf "$build/classes.jar" -C "$build/classes" .
& "$jdk/bin/java.exe" -cp "$bt/lib/d8.jar" com.android.tools.r8.D8 --lib $platform --min-api 26 --output "$build/dex" "$build/classes.jar"
if($LASTEXITCODE){throw 'd8 failed'}
Copy-Item "$build/base.apk" "$build/unsigned.apk" -Force
Push-Location "$build/dex"
& "$bt/aapt.exe" add "$build/unsigned.apk" classes.dex
if($LASTEXITCODE){throw 'add dex failed'}
Pop-Location
& "$bt/zipalign.exe" -f 4 "$build/unsigned.apk" "$build/aligned.apk"
if(!(Test-Path "$base/echo-local.keystore")) {
 & "$jdk/bin/keytool.exe" -genkeypair -keystore "$base/echo-local.keystore" -storepass android -keypass android -alias echo -keyalg RSA -keysize 2048 -validity 10000 -dname 'CN=Echo AirPlay Local Build'
}
& "$jdk/bin/java.exe" -jar "$bt/lib/apksigner.jar" sign --ks "$base/echo-local.keystore" --ks-pass pass:android --key-pass pass:android --out "$build/Echo-AirPlay.apk" "$build/aligned.apk"
if($LASTEXITCODE){throw 'sign failed'}
& "$jdk/bin/java.exe" -jar "$bt/lib/apksigner.jar" verify "$build/Echo-AirPlay.apk"
if($LASTEXITCODE){throw 'verify failed'}
