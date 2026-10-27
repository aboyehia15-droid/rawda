package com.rawda.app;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.PendingIntent;
import android.app.ProgressDialog;
import android.content.SharedPreferences;
import android.content.pm.PackageInstaller;
import android.provider.Settings;
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
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
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
                // accept every type the page asks for (PDF and images together), not only the first one
                Intent i = new Intent(Intent.ACTION_GET_CONTENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("*/*");
                List<String> types = new ArrayList<>();
                for (String t : p.getAcceptTypes()) for (String x : t.split(",")) { x = x.trim(); if (!x.isEmpty()) types.add(x.startsWith(".") ? "application/octet-stream" : x); }
                if (!types.isEmpty()) i.putExtra(Intent.EXTRA_MIME_TYPES, types.toArray(new String[0]));
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
        handleInstallStatus(getIntent());
        checkForUpdate();
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

    /* ================= self-update: ask, download, and hand the new version to Android's installer ================= */
    static final String RELEASES = "https://api.github.com/repos/aboyehia15-droid/rawda/releases/latest";
    static final String ACTION_INSTALL = "com.rawda.app.INSTALL_STATUS";
    String pendingApkUrl = null;

    int myVersion() {
        try { return getPackageManager().getPackageInfo(getPackageName(), 0).versionCode; } catch (Exception e) { return 0; }
    }

    void checkForUpdate() { checkForUpdate(false); }

    /** manual = the teacher pressed «تحديث البرنامج»: install right away, and say so when already up to date */
    void checkForUpdate(boolean manual) {
        new Thread(() -> {
            try {
                HttpURLConnection c = (HttpURLConnection) new URL(RELEASES).openConnection();
                c.setConnectTimeout(8000); c.setReadTimeout(8000);
                c.setRequestProperty("Accept", "application/vnd.github+json");
                if (c.getResponseCode() != 200) return;
                StringBuilder sb = new StringBuilder();
                try (InputStream in = c.getInputStream()) { byte[] buf = new byte[8192]; int n; while ((n = in.read(buf)) > 0) sb.append(new String(buf, 0, n, "UTF-8")); }
                JSONObject rel = new JSONObject(sb.toString());
                String tag = rel.optString("tag_name", "");
                int latest = Integer.parseInt(tag.replaceAll("[^0-9]", "").isEmpty() ? "0" : tag.replaceAll("[^0-9]", ""));
                if (latest <= myVersion()) { if (manual) runOnUiThread(() -> Toast.makeText(MainActivity.this, "التطبيق على أحدث نسخة، وتم تحديث محتوى البرنامج", Toast.LENGTH_LONG).show()); return; }
                String url = null;
                JSONArray assets = rel.optJSONArray("assets");
                if (assets != null) for (int i = 0; i < assets.length(); i++) { JSONObject a = assets.getJSONObject(i); if (a.optString("name").endsWith(".apk")) url = a.optString("browser_download_url"); }
                if (url == null) return;
                if (manual) { final String mu = url; runOnUiThread(() -> startUpdate(mu)); return; }
                SharedPreferences sp = getSharedPreferences("rawda", MODE_PRIVATE);
                if (tag.equals(sp.getString("later_tag", "")) && System.currentTimeMillis() - sp.getLong("later_at", 0) < 24L * 3600 * 1000) return;
                final String u = url, t = tag;
                runOnUiThread(() -> {
                    if (isFinishing()) return;
                    new AlertDialog.Builder(MainActivity.this)
                            .setTitle("يوجد تحديث لروضة الدروس")
                            .setMessage("نسخة أحدث من التطبيق جاهزة. هل تريد تحديثه الآن؟ لن تُحذف كتبك ولا تسجيلاتك.")
                            .setPositiveButton("تحديث", (d, w) -> startUpdate(u))
                            .setNegativeButton("لاحقًا", (d, w) -> sp.edit().putString("later_tag", t).putLong("later_at", System.currentTimeMillis()).apply())
                            .show();
                });
            } catch (Exception e) { if (manual) runOnUiThread(() -> Toast.makeText(MainActivity.this, "تعذّر فحص تحديث التطبيق، تأكد من الإنترنت", Toast.LENGTH_LONG).show()); }
        }).start();
    }

    void startUpdate(String url) {
        if (Build.VERSION.SDK_INT >= 26 && !getPackageManager().canRequestPackageInstalls()) {
            pendingApkUrl = url;
            Toast.makeText(this, "فعّل «السماح من هذا المصدر» لروضة الدروس، ثم ارجع للتطبيق", Toast.LENGTH_LONG).show();
            try { startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + getPackageName()))); } catch (Exception e) { openInBrowser(url); }
            return;
        }
        ProgressDialog pd = new ProgressDialog(this);
        pd.setMessage("جارٍ تنزيل التحديث…");
        pd.setCancelable(false);
        pd.show();
        new Thread(() -> {
            try {
                PackageInstaller pi = getPackageManager().getPackageInstaller();
                PackageInstaller.SessionParams params = new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);
                params.setAppPackageName(getPackageName());
                int sid = pi.createSession(params);
                PackageInstaller.Session session = pi.openSession(sid);
                HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
                c.setInstanceFollowRedirects(true);
                c.setConnectTimeout(15000); c.setReadTimeout(30000);
                try (InputStream in = c.getInputStream(); OutputStream out = session.openWrite("rawda.apk", 0, -1)) {
                    byte[] buf = new byte[65536]; int n; while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
                    session.fsync(out);
                }
                Intent st = new Intent(this, MainActivity.class).setAction(ACTION_INSTALL);
                int flags = PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 31 ? PendingIntent.FLAG_MUTABLE : 0);
                PendingIntent piStatus = PendingIntent.getActivity(this, sid, st, flags);
                session.commit(piStatus.getIntentSender());
                session.close();
                runOnUiThread(pd::dismiss);
            } catch (Exception e) {
                runOnUiThread(() -> { pd.dismiss(); Toast.makeText(MainActivity.this, "تعذّر التحديث من داخل التطبيق، سيُفتح رابط التنزيل", Toast.LENGTH_LONG).show(); openInBrowser(url); });
            }
        }).start();
    }

    void openInBrowser(String url) {
        try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); } catch (Exception ignored) { }
    }

    void handleInstallStatus(Intent it) {
        if (it == null || !ACTION_INSTALL.equals(it.getAction())) return;
        int status = it.getIntExtra(PackageInstaller.EXTRA_STATUS, -999);
        if (status == PackageInstaller.STATUS_PENDING_USER_ACTION) {
            Intent confirm = it.getParcelableExtra(Intent.EXTRA_INTENT);
            if (confirm != null) { confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK); try { startActivity(confirm); } catch (Exception ignored) { } }
        } else if (status != PackageInstaller.STATUS_SUCCESS && status != -999) {
            Toast.makeText(this, "لم يكتمل التحديث", Toast.LENGTH_LONG).show();
        }
    }

    @Override
    protected void onNewIntent(Intent it) { super.onNewIntent(it); setIntent(it); handleInstallStatus(it); }

    @Override
    protected void onResume() {
        super.onResume();
        if (pendingApkUrl != null && (Build.VERSION.SDK_INT < 26 || getPackageManager().canRequestPackageInstalls())) { String u = pendingApkUrl; pendingApkUrl = null; startUpdate(u); }
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

        /** «تحديث البرنامج»: fresh content (no stored copies), then the newest app version if there is one */
        @JavascriptInterface
        public void updateNow() {
            runOnUiThread(() -> {
                try { web.clearCache(true); } catch (Exception ignored) { }
                web.loadUrl(HOME + (HOME.contains("?") ? "&" : "?") + "v=" + System.currentTimeMillis());
                checkForUpdate(true);
            });
        }

        @JavascriptInterface
        public int appVersion() { return myVersion(); }

        /** «خروج»: close the program completely */
        @JavascriptInterface
        public void exitApp() {
            runOnUiThread(() -> {
                try { if (tts != null) tts.stop(); } catch (Exception ignored) { }
                if (Build.VERSION.SDK_INT >= 21) finishAndRemoveTask(); else finish();
            });
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
