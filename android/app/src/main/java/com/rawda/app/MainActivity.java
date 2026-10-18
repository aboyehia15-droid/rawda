package com.rawda.app;

import android.Manifest;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ContentValues;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;
import android.util.Base64;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** روضة الدروس: a full-screen window onto the always-updated online program. */
public class MainActivity extends Activity {
    static final String HOME = "https://aboyehia15-droid.github.io/rawda/";
    static final int REQ_FILE = 1, REQ_MIC = 2;

    WebView web;
    FrameLayout root;
    View customView;
    WebChromeClient.CustomViewCallback customCb;
    ValueCallback<Uri[]> fileCb;
    PermissionRequest pendingPerm;
    TextToSpeech tts;
    boolean ttsReady = false;
    final List<String[]> ttsQueue = new ArrayList<>();

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        root = new FrameLayout(this);
        web = new WebView(this);
        root.addView(web, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(root);
        immersive();

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(true);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setSupportZoom(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        web.addJavascriptInterface(new Bridge(), "RawdaAndroid");

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                String u = r.getUrl().toString();
                if (u.startsWith(HOME) || u.startsWith("blob:") || u.startsWith("data:") || u.startsWith("about:")) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, r.getUrl())); } catch (ActivityNotFoundException e) { /* nothing to open it */ }
                return true;
            }
            @Override
            public void onReceivedError(WebView v, WebResourceRequest r, WebResourceError e) {
                if (r.isForMainFrame()) showOffline();
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> cb, FileChooserParams p) {
                if (fileCb != null) fileCb.onReceiveValue(null);
                fileCb = cb;
                Intent i = p.createIntent();
                i.addCategory(Intent.CATEGORY_OPENABLE);
                if (p.getMode() == FileChooserParams.MODE_OPEN_MULTIPLE) i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                try { startActivityForResult(Intent.createChooser(i, "اختر الملفات"), REQ_FILE); }
                catch (ActivityNotFoundException e) { fileCb = null; return false; }
                return true;
            }
            @Override
            public void onPermissionRequest(PermissionRequest req) {
                runOnUiThread(() -> {
                    boolean audio = false;
                    for (String r : req.getResources()) if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(r)) audio = true;
                    if (!audio) { req.deny(); return; }
                    if (Build.VERSION.SDK_INT >= 23 && checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                        pendingPerm = req;
                        requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQ_MIC);
                    } else {
                        req.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
                    }
                });
            }
            @Override
            public void onShowCustomView(View view, CustomViewCallback cb) {
                if (customView != null) { cb.onCustomViewHidden(); return; }
                customView = view; customCb = cb;
                root.addView(view, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
                web.setVisibility(View.GONE);
                immersive();
            }
            @Override
            public void onHideCustomView() {
                if (customView == null) return;
                root.removeView(customView);
                customView = null;
                web.setVisibility(View.VISIBLE);
                if (customCb != null) customCb.onCustomViewHidden();
                customCb = null;
                immersive();
            }
        });

        tts = new TextToSpeech(this, status -> {
            ttsReady = status == TextToSpeech.SUCCESS;
            if (ttsReady) {
                tts.setLanguage(new Locale("ar"));
                synchronized (ttsQueue) { for (String[] q : ttsQueue) speakNow(q); ttsQueue.clear(); }
                web.post(() -> web.evaluateJavascript("window.__rawdaVoicesReady&&__rawdaVoicesReady()", null));
            }
        });
        tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
            @Override public void onStart(String id) { js(id, "start"); }
            @Override public void onDone(String id) { js(id, "end"); }
            @Override public void onError(String id) { js(id, "error"); }
            @Override public void onStop(String id, boolean interrupted) { js(id, "end"); }
        });

        if (b != null) web.restoreState(b); else web.loadUrl(HOME);
    }

    void js(String id, String ev) {
        web.post(() -> web.evaluateJavascript("window.__rawdaTTS&&__rawdaTTS(" + JSONObject.quote(id) + ",'" + ev + "')", null));
    }

    void speakNow(String[] q) {
        String text = q[0], lang = q[1], voice = q[4], id = q[5];
        float rate = 1f, pitch = 1f;
        try { rate = Float.parseFloat(q[2]); pitch = Float.parseFloat(q[3]); } catch (Exception ignored) { }
        boolean set = false;
        if (voice != null && !voice.isEmpty() && Build.VERSION.SDK_INT >= 21) {
            try { for (Voice v : tts.getVoices()) if (v.getName().equals(voice)) { tts.setVoice(v); set = true; break; } } catch (Exception ignored) { }
        }
        if (!set) tts.setLanguage(Locale.forLanguageTag(lang == null || lang.isEmpty() ? "ar" : lang));
        tts.setSpeechRate(rate);
        tts.setPitch(pitch);
        Bundle p = new Bundle();
        p.putString(TextToSpeech.Engine.KEY_PARAM_UTTERANCE_ID, id);
        tts.speak(text, TextToSpeech.QUEUE_ADD, p, id);
    }

    void showOffline() {
        String html = "<!doctype html><html dir='rtl' lang='ar'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                + "<style>body{font-family:sans-serif;background:#f3f6f8;color:#1d2b36;display:grid;place-items:center;min-height:100vh;margin:0;text-align:center;padding:16px}"
                + "button{font-size:1.2rem;padding:14px 26px;border:0;border-radius:14px;background:#2a9d8f;color:#fff}</style></head><body><div>"
                + "<h1>روضة الدروس</h1><p>لا يوجد اتصال بالإنترنت.<br>تأكد من اتصال الشاشة بالشبكة ثم اضغط «إعادة المحاولة».</p>"
                + "<button onclick=\"location.href='" + HOME + "'\">إعادة المحاولة</button></div></body></html>";
        web.loadDataWithBaseURL(HOME, html, "text/html", "utf-8", HOME);
    }

    void immersive() {
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN);
    }

    @Override
    public void onWindowFocusChanged(boolean f) { super.onWindowFocusChanged(f); if (f) immersive(); }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        if (req == REQ_FILE) {
            if (fileCb == null) return;
            Uri[] out = null;
            if (res == RESULT_OK && data != null) {
                if (data.getClipData() != null) {
                    int n = data.getClipData().getItemCount();
                    out = new Uri[n];
                    for (int i = 0; i < n; i++) out[i] = data.getClipData().getItemAt(i).getUri();
                } else if (data.getData() != null) out = new Uri[]{data.getData()};
            }
            fileCb.onReceiveValue(out);
            fileCb = null;
            return;
        }
        super.onActivityResult(req, res, data);
    }

    @Override
    public void onRequestPermissionsResult(int req, String[] perms, int[] res) {
        if (req == REQ_MIC && pendingPerm != null) {
            if (res.length > 0 && res[0] == PackageManager.PERMISSION_GRANTED) pendingPerm.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
            else pendingPerm.deny();
            pendingPerm = null;
        }
    }

    @Override
    public void onBackPressed() {
        if (customView != null) { web.getWebChromeClient().onHideCustomView(); return; }
        if (web.canGoBack()) web.goBack(); else super.onBackPressed();
    }

    @Override
    protected void onSaveInstanceState(Bundle out) { super.onSaveInstanceState(out); web.saveState(out); }

    @Override
    protected void onDestroy() { if (tts != null) tts.shutdown(); web.destroy(); super.onDestroy(); }

    /** Functions the program page can call: Arabic speech through Android's own voice, and saving files. */
    class Bridge {
        @JavascriptInterface
        public void speak(String text, String lang, String rate, String pitch, String voice, String id) {
            String[] q = {text, lang, rate, pitch, voice, id};
            if (!ttsReady) { synchronized (ttsQueue) { ttsQueue.add(q); } return; }
            speakNow(q);
        }

        @JavascriptInterface
        public void stop() { if (tts != null) tts.stop(); synchronized (ttsQueue) { ttsQueue.clear(); } }

        @JavascriptInterface
        public String voices() {
            JSONArray a = new JSONArray();
            if (!ttsReady || Build.VERSION.SDK_INT < 21) return a.toString();
            try {
                for (Voice v : tts.getVoices()) {
                    if (v.isNetworkConnectionRequired() && v.getFeatures() != null && v.getFeatures().contains(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED)) continue;
                    JSONObject o = new JSONObject();
                    o.put("name", v.getName());
                    o.put("lang", v.getLocale().toLanguageTag());
                    a.put(o);
                }
            } catch (Exception ignored) { }
            return a.toString();
        }

        @JavascriptInterface
        public boolean saveBase64(String filename, String b64, String mime) {
            try {
                byte[] bytes = Base64.decode(b64, Base64.DEFAULT);
                if (mime == null || mime.isEmpty()) mime = "application/octet-stream";
                if (Build.VERSION.SDK_INT >= 29) {
                    ContentValues cv = new ContentValues();
                    cv.put(MediaStore.MediaColumns.DISPLAY_NAME, filename);
                    cv.put(MediaStore.MediaColumns.MIME_TYPE, mime);
                    cv.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/روضة الدروس");
                    Uri uri = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv);
                    if (uri == null) throw new Exception("insert");
                    try (OutputStream os = getContentResolver().openOutputStream(uri)) { os.write(bytes); }
                } else {
                    if (checkSelfPermissionCompat()) {
                        File dir = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "روضة الدروس");
                        dir.mkdirs();
                        try (FileOutputStream os = new FileOutputStream(new File(dir, filename))) { os.write(bytes); }
                    } else {
                        File dir = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
                        try (FileOutputStream os = new FileOutputStream(new File(dir, filename))) { os.write(bytes); }
                    }
                }
                runOnUiThread(() -> Toast.makeText(MainActivity.this, "حُفظ في مجلد التنزيلات ← روضة الدروس", Toast.LENGTH_LONG).show());
                return true;
            } catch (Exception e) {
                runOnUiThread(() -> Toast.makeText(MainActivity.this, "تعذّر الحفظ", Toast.LENGTH_LONG).show());
                return false;
            }
        }
    }

    boolean checkSelfPermissionCompat() {
        if (Build.VERSION.SDK_INT < 23) return true;
        if (checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED) return true;
        requestPermissions(new String[]{Manifest.permission.WRITE_EXTERNAL_STORAGE}, 3);
        return false;
    }
}
