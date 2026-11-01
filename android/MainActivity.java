package io.blue1ms.echoairplay;

import android.app.Activity;
import android.os.Bundle;
import android.app.AlertDialog;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import org.json.JSONObject;
import android.os.Handler;
import android.content.Intent;
import android.content.pm.ShortcutInfo;
import android.content.pm.ShortcutManager;
import android.graphics.Color;
import android.graphics.drawable.Icon;
import android.view.View;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceError;
import android.webkit.WebView;
import android.webkit.WebChromeClient;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {
 private WebView web;
 private final Handler handler = new Handler();
 private boolean destroyed = false;
 private String pendingBackup;
 private static final int SAVE_BACKUP=6101, OPEN_BACKUP=6102;
 private static final String URL = "http://127.0.0.1:8765/";
 private boolean local(String url) {return url.startsWith(URL);}
 @Override public void onCreate(Bundle state) {
  super.onCreate(state);
  getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
  getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN);
  web = new WebView(this);
  web.setBackgroundColor(Color.rgb(16,18,21));
  web.getSettings().setJavaScriptEnabled(true);
  web.getSettings().setDomStorageEnabled(true);
  web.getSettings().setAllowFileAccess(false);
  web.getSettings().setAllowContentAccess(false);
  web.getSettings().setSupportZoom(false);
  web.getSettings().setTextZoom(100);
  web.setOverScrollMode(View.OVER_SCROLL_NEVER);
  web.addJavascriptInterface(new Display(), "EchoDisplay");
  web.setWebChromeClient(new WebChromeClient());
  web.setWebViewClient(new WebViewClient() {
   @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {return !local(request.getUrl().toString());}
   @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
    if(request.isForMainFrame()) {
     view.loadDataWithBaseURL(URL,"<html><body style='background:#101215;color:#bcebd8;font:24px sans-serif;text-align:center;padding:15vh'>Echo AirPlay<p style='font-size:17px;color:#b1b8bc'>Waiting for the local receiver…</p></body></html>","text/html","UTF-8",null);
     handler.postDelayed(() -> {if(!destroyed) web.loadUrl(URL);},3000);
    }
   }
  });
  setContentView(web);
  immersive();
  web.loadUrl(URL);
 }
 private void immersive() {getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN|View.SYSTEM_UI_FLAG_HIDE_NAVIGATION|View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY|View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN|View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION|View.SYSTEM_UI_FLAG_LAYOUT_STABLE);}
 @Override public void onWindowFocusChanged(boolean focus) {super.onWindowFocusChanged(focus);if(focus) immersive();}
 @Override public void onBackPressed() {web.evaluateJavascript("document.getElementById('info').hidden=true;document.getElementById('night').hidden=true;",null);new Display().dim(false);}
 private void backupMessage(String message) {web.evaluateJavascript("window.backupResult && window.backupResult("+JSONObject.quote(message)+");",null);}
 @Override protected void onActivityResult(int requestCode,int resultCode,Intent data) {
  super.onActivityResult(requestCode,resultCode,data);
  if(requestCode!=SAVE_BACKUP&&requestCode!=OPEN_BACKUP)return;
  if(resultCode!=RESULT_OK||data==null||data.getData()==null){pendingBackup=null;return;}
  try {
   if(requestCode==SAVE_BACKUP){
    if(pendingBackup==null)throw new Exception("Please save the backup again.");
    try(OutputStream output=getContentResolver().openOutputStream(data.getData(),"wt")){
     if(output==null)throw new Exception("Cannot open the selected file.");
     output.write(pendingBackup.getBytes(StandardCharsets.UTF_8));
    }
    backupMessage("Backup saved. Keep pairing credentials private.");
   } else {
    ByteArrayOutputStream bytes=new ByteArrayOutputStream();
    try(InputStream input=getContentResolver().openInputStream(data.getData())){
     if(input==null)throw new Exception("Cannot read the selected file.");
     byte[] buffer=new byte[4096];int count;
     while((count=input.read(buffer))!=-1){if(bytes.size()+count>65536)throw new Exception("Backup exceeds 64 KiB.");bytes.write(buffer,0,count);}
    }
    String text=new String(bytes.toByteArray(),StandardCharsets.UTF_8);
    web.evaluateJavascript("window.receiveBackup && window.receiveBackup("+JSONObject.quote(text)+");",null);
   }
  } catch(Exception error){backupMessage(error.getMessage()==null?"Backup operation failed.":error.getMessage());}
  finally {pendingBackup=null;}
 }
 public class Display {
  @JavascriptInterface public void saveBackup(String json) {runOnUiThread(() -> {
   try {
    if(json.getBytes(StandardCharsets.UTF_8).length>65536||!new JSONObject(json).optString("format").equals("echo-airplay-touch"))throw new Exception("Invalid backup");
    pendingBackup=json;
    Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/json").putExtra(Intent.EXTRA_TITLE,"echo-airplay-backup.json");
    startActivityForResult(intent,SAVE_BACKUP);
   }catch(Exception error){pendingBackup=null;backupMessage("Unable to open the backup file picker.");}
  });}
  @JavascriptInterface public void openBackup() {runOnUiThread(() -> {
   try{startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*"),OPEN_BACKUP);}
   catch(Exception error){backupMessage("Unable to open the backup file picker.");}
  });}

  @JavascriptInterface public void dim(boolean dim) {runOnUiThread(() -> {WindowManager.LayoutParams p=getWindow().getAttributes();p.screenBrightness=dim?0.01f:-1f;getWindow().setAttributes(p);});}
  @JavascriptInterface public void pin() {runOnUiThread(() -> {ShortcutManager sm=getSystemService(ShortcutManager.class);if(sm!=null&&sm.isRequestPinShortcutSupported()){Intent launch=new Intent(MainActivity.this,MainActivity.class).setAction(Intent.ACTION_VIEW);ShortcutInfo info=new ShortcutInfo.Builder(MainActivity.this,"echo-airplay").setShortLabel("Echo AirPlay").setIcon(Icon.createWithResource(MainActivity.this,io.blue1ms.echoairplay.R.drawable.icon)).setIntent(launch).build();sm.requestPinShortcut(info,null);}});}
 }
 @Override protected void onDestroy(){destroyed=true;handler.removeCallbacksAndMessages(null);web.destroy();super.onDestroy();}
}
