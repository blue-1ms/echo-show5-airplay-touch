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
 private WebView home,library;
 private Button libraryButton;
 private LinearLayout tabs;
 private boolean libraryVisible=false;
 private boolean fullLibrary=false;
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
  tabs=new LinearLayout(activity);tabs.setGravity(android.view.Gravity.CENTER);
  musicButton=button("AirPlay",()->showMusic());libraryButton=button("Library",()->showLibrary());homeButton=button("Home",()->showHome());
  for(Button tab:new Button[]{musicButton,libraryButton,homeButton}){tab.setMinHeight(0);tab.setMinimumHeight(0);tab.setMinWidth(0);tab.setMinimumWidth(0);tab.setPadding(dp(8),0,dp(8),0);tabs.addView(tab,new LinearLayout.LayoutParams(dp(76),dp(40)));}
  FrameLayout shell=new FrameLayout(activity);shell.addView(root,new FrameLayout.LayoutParams(-1,-1));
  FrameLayout.LayoutParams bar=new FrameLayout.LayoutParams(-2,dp(40),android.view.Gravity.TOP|android.view.Gravity.CENTER_HORIZONTAL);bar.topMargin=dp(8);shell.addView(tabs,bar);
  activity.setContentView(shell);navigation();

 }
 void connections(){new AlertDialog.Builder(activity).setTitle("Connections").setItems(new String[]{"Home Assistant","Music Assistant"},(d,w)->{if(w==0)configure();else configureLibrary();}).show();}
 private int dp(int value){return Math.round(value*activity.getResources().getDisplayMetrics().density);}
 private Button button(String text,Runnable action){Button b=new Button(activity);b.setText(text);b.setTextSize(14);b.setAllCaps(false);b.setTextColor(Color.WHITE);b.setBackground(background(false));b.setOnClickListener(v->action.run());return b;}
 private GradientDrawable background(boolean selected){GradientDrawable bg=new GradientDrawable();bg.setColor(selected?Color.rgb(35,66,56):Color.rgb(25,29,33));bg.setCornerRadius(dp(12));return bg;}
 private void navigation(){
  boolean hasHome=!url.isEmpty(),hasLibrary=!preferences.getString("ma-url","").isEmpty();
  tabs.setVisibility(hasHome||hasLibrary?View.VISIBLE:View.GONE);homeButton.setVisibility(hasHome?View.VISIBLE:View.GONE);libraryButton.setVisibility(hasLibrary?View.VISIBLE:View.GONE);
  boolean external=visible||libraryVisible;pages.setPadding(0,external?dp(52):0,0,0);
  for(Button tab:new Button[]{musicButton,libraryButton,homeButton}){
   boolean selected=tab==musicButton?!external:tab==libraryButton?libraryVisible:visible;
   tab.setTextColor(selected?Color.rgb(127,224,186):Color.rgb(157,165,169));tab.setBackgroundColor(Color.TRANSPARENT);
   GradientDrawable line=new GradientDrawable();line.setColor(selected?Color.rgb(127,224,186):Color.TRANSPARENT);line.setBounds(0,0,dp(28),dp(2));tab.setCompoundDrawables(null,null,null,line);
  }
 }

 static String validate(String value){
  Uri u=Uri.parse(value.trim());String scheme=u.getScheme(),host=u.getHost();
  if((!"http".equals(scheme)&&!"https".equals(scheme))||host==null||host.isEmpty()||u.getUserInfo()!=null||u.getQuery()!=null||u.getFragment()!=null)throw new IllegalArgumentException("Use an http(s) server/dashboard URL without credentials, query or fragment.");
  if("127.0.0.1".equals(host)||"localhost".equalsIgnoreCase(host)||"::1".equals(host)||"[::1]".equals(host))throw new IllegalArgumentException("Use the Home Assistant network address, not this Echo's local receiver.");
  return u.toString();
 }
 private int port(Uri u){return u.getPort()!=-1?u.getPort():("https".equals(u.getScheme())?443:80);}
 private boolean sameOrigin(String value){try{Uri a=Uri.parse(url),b=Uri.parse(value);return a.getScheme().equals(b.getScheme())&&a.getHost().equalsIgnoreCase(b.getHost())&&port(a)==port(b);}catch(Exception e){return false;}}
 void showMusic(){libraryVisible=false;if(library!=null)library.setVisibility(View.GONE);visible=false;if(home!=null)home.setVisibility(View.GONE);music.setVisibility(View.VISIBLE);navigation();}
 boolean back(){if(!visible&&!libraryVisible)return false;showMusic();return true;}
 boolean isVisible(){return visible||libraryVisible;}
 private void showHome(){
  libraryVisible=false;if(library!=null)library.setVisibility(View.GONE);
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

 private void showLibrary(){
  if(library!=null&&fullLibrary){fullLibrary=false;loadLibrary(preferences.getString("ma-url",""));}
  String address=preferences.getString("ma-url","");
  if(address.isEmpty()){configureLibrary();return;}
  if(library==null){
   library=new WebView(activity);library.setBackgroundColor(Color.rgb(16,18,21));
   library.getSettings().setJavaScriptEnabled(true);library.getSettings().setDomStorageEnabled(true);
   library.getSettings().setUseWideViewPort(true);library.getSettings().setLoadWithOverviewMode(true);
   library.getSettings().setAllowFileAccess(false);library.getSettings().setAllowContentAccess(false);
   library.setWebChromeClient(new WebChromeClient());final Uri origin=Uri.parse(address);
   library.setWebViewClient(new WebViewClient(){
    @Override public void onPageFinished(WebView v,String page){if(fullLibrary)v.evaluateJavascript("(function(){var m=document.querySelector('meta[name=viewport]');if(m)m.content='width=1100';window.dispatchEvent(new Event('resize'));})()",null);}

    @Override public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest r){Uri u=r.getUrl();if("/__echo_full_ma".equals(u.getPath())&&origin.getHost().equalsIgnoreCase(u.getHost())&&port(origin)==port(u)&&origin.getScheme().equals(u.getScheme())){fullLibrary=true;v.loadUrl(address);return true;}return !(origin.getScheme().equals(u.getScheme())&&origin.getHost().equalsIgnoreCase(u.getHost())&&port(origin)==port(u));}
    @Override public void onReceivedError(WebView v,WebResourceRequest r,WebResourceError e){if(r.isForMainFrame()&&!activity.isFinishing())new AlertDialog.Builder(activity).setTitle("Music Assistant unavailable").setMessage("Check your server address and connection.").setPositiveButton("Retry",(d,w)->v.reload()).setNegativeButton("AirPlay",(d,w)->showMusic()).show();}
   });pages.addView(library,new FrameLayout.LayoutParams(-1,-1));loadLibrary(address);
  }
  visible=false;libraryVisible=true;music.setVisibility(View.GONE);if(home!=null)home.setVisibility(View.GONE);library.setVisibility(View.VISIBLE);navigation();
 }
 private void loadLibrary(String address){
  try{java.io.InputStream in=activity.getAssets().open("echo-library.html");java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream();byte[] b=new byte[4096];int n;while((n=in.read(b))!=-1)out.write(b,0,n);in.close();library.loadDataWithBaseURL(address+"/__echo_touch/",out.toString("UTF-8"),"text/html","UTF-8",null);}catch(java.io.IOException e){fullLibrary=true;library.loadUrl(address);}
 }
 private void configureLibrary(){
  EditText input=new EditText(activity);input.setSingleLine(true);input.setHint("http://music-assistant.local:8095");input.setText(preferences.getString("ma-url",""));
  AlertDialog dialog=new AlertDialog.Builder(activity).setTitle("Music Assistant server (optional)").setView(input).setPositiveButton("Save",null).setNegativeButton("Cancel",null).setNeutralButton("Disconnect",(d,w)->{preferences.edit().remove("ma-url").apply();discardLibrary();showMusic();}).create();
  dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{try{String next=validate(input.getText().toString());preferences.edit().putString("ma-url",next).apply();discardLibrary();dialog.dismiss();showLibrary();}catch(IllegalArgumentException e){input.setError(e.getMessage());}}));dialog.show();
 }
 private void discardLibrary(){if(library!=null){pages.removeView(library);library.destroy();library=null;}}

 void destroy(){discard();discardLibrary();}
}
