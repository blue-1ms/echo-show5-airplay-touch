package io.blue1ms.echoairplay;

import android.app.Activity;
import android.os.Bundle;
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
import android.webkit.WebViewClient;

public class MainActivity extends Activity {
 private WebView web;
 private final Handler handler = new Handler();
 private boolean destroyed = false;
 private static final String URL = "http://127.0.0.1:8765/";
 private boolean local(String url) {return url.startsWith(URL);}
 @Override public void onCreate(Bundle state) {
  super.onCreate(state);
  getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
  getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN);
  web = new WebView(this);
  web.setBackgroundColor(Color.rgb(16,18,21));
  web.getSettings().setJavaScriptEnabled(true);
  web.getSettings().setAllowFileAccess(false);
  web.getSettings().setAllowContentAccess(false);
  web.getSettings().setSupportZoom(false);
  web.getSettings().setTextZoom(100);
  web.setOverScrollMode(View.OVER_SCROLL_NEVER);
  web.addJavascriptInterface(new Display(), "EchoDisplay");
  web.setWebViewClient(new WebViewClient() {
   @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {return !local(request.getUrl().toString());}
   @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
    if(request.isForMainFrame()) {
     view.loadDataWithBaseURL(URL,"<html><body style='background:#101215;color:#bcebd8;font:24px sans-serif;text-align:center;padding:15vh'>Echo AirPlay<p style='font-size:17px;color:#b1b8bc'>正在等待本机接收服务启动…</p></body></html>","text/html","UTF-8",null);
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
 public class Display {
  @JavascriptInterface public void dim(boolean dim) {runOnUiThread(() -> {WindowManager.LayoutParams p=getWindow().getAttributes();p.screenBrightness=dim?0.01f:-1f;getWindow().setAttributes(p);});}
  @JavascriptInterface public void pin() {runOnUiThread(() -> {ShortcutManager sm=getSystemService(ShortcutManager.class);if(sm!=null&&sm.isRequestPinShortcutSupported()){Intent launch=new Intent(MainActivity.this,MainActivity.class).setAction(Intent.ACTION_VIEW);ShortcutInfo info=new ShortcutInfo.Builder(MainActivity.this,"echo-airplay").setShortLabel("Echo AirPlay").setIcon(Icon.createWithResource(MainActivity.this,io.blue1ms.echoairplay.R.drawable.icon)).setIntent(launch).build();sm.requestPinShortcut(info,null);}});}
 }
 @Override protected void onDestroy(){destroyed=true;handler.removeCallbacksAndMessages(null);web.destroy();super.onDestroy();}
}
