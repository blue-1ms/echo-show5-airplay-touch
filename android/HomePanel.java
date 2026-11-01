package io.blue1ms.echoairplay;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.text.InputType;
import android.view.View;
import android.view.WindowManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Optional HA frontend. No receiver JavascriptInterface is exposed to this WebView. */
final class HomePanel {
 private final Activity activity;
 private final WebView music;
 private WebView home;
 private final FrameLayout pages;
 private final Button musicButton,homeButton;
 private final SharedPreferences preferences;
 private String url;
 private boolean visible=false, errorShown=false;
 HomePanel(Activity activity,WebView music){
  this.activity=activity;this.music=music;
  preferences=activity.getSharedPreferences("home-panel",Activity.MODE_PRIVATE);
  url=preferences.getString("url","");
  LinearLayout root=new LinearLayout(activity);root.setOrientation(LinearLayout.VERTICAL);root.setBackgroundColor(Color.rgb(16,18,21));
  pages=new FrameLayout(activity);pages.addView(music,new FrameLayout.LayoutParams(-1,-1));
  root.addView(pages,new LinearLayout.LayoutParams(-1,0,1));
  LinearLayout dock=new LinearLayout(activity);dock.setPadding(dp(12),dp(3),dp(12),dp(3));
  musicButton=button("Music",()->showMusic());homeButton=button("Home",()->showHome());
  dock.addView(musicButton,new LinearLayout.LayoutParams(0,-1,1));
  dock.addView(homeButton,new LinearLayout.LayoutParams(0,-1,1));
  dock.addView(button("Setup",()->configure()),new LinearLayout.LayoutParams(dp(96),-1));
  root.addView(dock,new LinearLayout.LayoutParams(-1,dp(54)));
  activity.setContentView(root);navigation();
 }
 private int dp(int value){return Math.round(value*activity.getResources().getDisplayMetrics().density);}
 private Button button(String text,Runnable action){Button b=new Button(activity);b.setText(text);b.setTextSize(17);b.setAllCaps(false);b.setTextColor(Color.WHITE);b.setBackground(background(false));b.setOnClickListener(v->action.run());return b;}
 private GradientDrawable background(boolean selected){GradientDrawable bg=new GradientDrawable();bg.setColor(selected?Color.rgb(35,66,56):Color.rgb(25,29,33));bg.setCornerRadius(dp(12));bg.setStroke(dp(1),selected?Color.rgb(87,139,119):Color.rgb(45,51,55));return bg;}
 private void navigation(){musicButton.setTextColor(visible?Color.LTGRAY:Color.rgb(127,224,186));homeButton.setTextColor(visible?Color.rgb(127,224,186):Color.LTGRAY);musicButton.setBackground(background(!visible));homeButton.setBackground(background(visible));}
 static String validate(String value){
  Uri u=Uri.parse(value.trim());String scheme=u.getScheme(),host=u.getHost();
  if((!"http".equals(scheme)&&!"https".equals(scheme))||host==null||host.isEmpty()||u.getUserInfo()!=null||u.getQuery()!=null||u.getFragment()!=null)throw new IllegalArgumentException("Use an http(s) server/dashboard URL without credentials, query or fragment.");
  if("127.0.0.1".equals(host)||"localhost".equalsIgnoreCase(host)||"::1".equals(host)||"[::1]".equals(host))throw new IllegalArgumentException("Use the Home Assistant network address, not this Echo's local receiver.");
  return u.toString();
 }
 private int port(Uri u){return u.getPort()!=-1?u.getPort():("https".equals(u.getScheme())?443:80);}
 private boolean sameOrigin(String value){try{Uri a=Uri.parse(url),b=Uri.parse(value);return a.getScheme().equals(b.getScheme())&&a.getHost().equalsIgnoreCase(b.getHost())&&port(a)==port(b);}catch(Exception e){return false;}}
 void showMusic(){visible=false;if(home!=null)home.setVisibility(View.GONE);music.setVisibility(View.VISIBLE);navigation();}
 boolean back(){if(!visible)return false;showMusic();return true;}
 boolean isVisible(){return visible;}
 private void showHome(){
  if(url.isEmpty()){configure();return;}
  if(home==null){
   home=new WebView(activity);home.setBackgroundColor(Color.rgb(16,18,21));
   home.getSettings().setJavaScriptEnabled(true);home.getSettings().setDomStorageEnabled(true);
   home.getSettings().setAllowFileAccess(false);home.getSettings().setAllowContentAccess(false);home.getSettings().setTextZoom(100);
   home.setWebChromeClient(new WebChromeClient());
   home.setWebViewClient(new WebViewClient(){
    @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){return !sameOrigin(request.getUrl().toString());}
    @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error){
     if(request.isForMainFrame()&&!errorShown&&!activity.isFinishing()){
      errorShown=true;new AlertDialog.Builder(activity).setTitle("Home Assistant unavailable").setMessage("Check the network and server address. Music is still available.").setPositiveButton("Retry",(d,w)->{errorShown=false;if(home!=null)home.loadUrl(url);}).setNegativeButton("Music",(d,w)->showMusic()).setOnDismissListener(d->errorShown=false).show();
     }
    }
   });
   pages.addView(home,new FrameLayout.LayoutParams(-1,-1));home.loadUrl(url);
  }
  visible=true;music.setVisibility(View.GONE);home.setVisibility(View.VISIBLE);navigation();
  WindowManager.LayoutParams p=activity.getWindow().getAttributes();p.screenBrightness=-1f;activity.getWindow().setAttributes(p);
 }
 private void configure(){
  LinearLayout form=new LinearLayout(activity);form.setOrientation(LinearLayout.VERTICAL);form.setPadding(dp(20),dp(8),dp(20),dp(8));
  TextView help=new TextView(activity);help.setText("Optional Home Assistant server/dashboard URL. Sign in on the Home page. A dedicated non-admin account is recommended for a shared screen. Use HTTPS on untrusted networks.");form.addView(help);
  EditText input=new EditText(activity);input.setSingleLine(true);input.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);input.setHint("http://homeassistant.local:8123/echo-home");input.setText(url);form.addView(input);
  AlertDialog dialog=new AlertDialog.Builder(activity).setTitle("Home setup").setView(form).setPositiveButton("Save",null).setNegativeButton("Cancel",null).setNeutralButton("Disconnect",(d,w)->{preferences.edit().remove("url").apply();url="";discard();showMusic();}).create();
  dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{try{
   String next=validate(input.getText().toString());preferences.edit().putString("url",next).apply();url=next;discard();dialog.dismiss();showHome();
  }catch(IllegalArgumentException e){input.setError(e.getMessage());}}));dialog.show();
 }
 private void discard(){if(home!=null){pages.removeView(home);home.destroy();home=null;}}
 void destroy(){discard();}
}
