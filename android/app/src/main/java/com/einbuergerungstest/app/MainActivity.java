package com.einbuergerungstest.app;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.io.IOException;
import java.io.InputStream;
import java.util.HashMap;
import java.util.Map;

/**
 * The whole app: one WebView showing the offline question trainer.
 *
 * <p><b>Why the page is served from a made-up https origin instead of
 * {@code file:///android_asset/}.</b> A {@code file://} page is an opaque
 * origin, and WebView refuses {@code localStorage} on opaque origins — the
 * adaptive part of the trainer (which questions you got wrong, so they come
 * back more often) would silently stop working and there would be nothing on
 * screen to say why. Serving the same bytes from {@code https} gives the page a
 * real, stable origin, so its storage behaves exactly as it does in a browser.
 *
 * <p>Nothing is fetched over that origin. Every request is answered from the
 * APK by {@link LocalAssets} below, and the app does not ask for the INTERNET
 * permission at all, so a request that was not intercepted cannot quietly
 * succeed.
 */
public class MainActivity extends Activity {

    /** The origin the page believes it is on. Never resolved over the network. */
    private static final String ORIGIN = "https://einbuergerungstest.local";

    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        webView = new WebView(this);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        // Required for the learning state to survive closing the app.
        settings.setDomStorageEnabled(true);
        // The page has no business reaching the filesystem or content providers.
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);

        webView.setWebViewClient(new LocalAssets());

        setContentView(webView);
        if (savedInstanceState != null) {
            webView.restoreState(savedInstanceState);
        } else {
            webView.loadUrl(ORIGIN + "/index.html");
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        webView.saveState(outState);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    /** Answers every request for {@link #ORIGIN} from the APK's assets. */
    private class LocalAssets extends WebViewClient {

        @Override
        public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
            return serve(request.getUrl() == null ? null : request.getUrl().toString());
        }

        /** Keeps the trainer from wandering off to anywhere else. */
        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            String url = request.getUrl() == null ? null : request.getUrl().toString();
            return !(url != null && url.startsWith(ORIGIN + "/"));
        }

        private WebResourceResponse serve(String url) {
            if (url == null || !url.startsWith(ORIGIN + "/")) {
                return null; // not ours: let the WebView do what it likes, which cannot succeed
            }

            String path = url.substring((ORIGIN + "/").length());
            int cut = path.indexOf('?');
            if (cut >= 0) {
                path = path.substring(0, cut);
            }
            cut = path.indexOf('#');
            if (cut >= 0) {
                path = path.substring(0, cut);
            }
            if (path.isEmpty()) {
                path = "index.html";
            }
            // Assets are addressed by a fixed name here; refuse anything that
            // tries to climb out of the folder.
            if (path.contains("..")) {
                return notFound();
            }

            InputStream stream;
            try {
                stream = getAssets().open(path);
            } catch (IOException missing) {
                return notFound();
            }

            String mime = mimeOf(path);
            boolean textual = mime.startsWith("text/") || mime.contains("javascript")
                    || mime.contains("json") || mime.contains("svg");
            return new WebResourceResponse(mime, textual ? "utf-8" : null, stream);
        }

        private WebResourceResponse notFound() {
            return new WebResourceResponse(
                    "text/plain", "utf-8", 404, "Not Found",
                    new HashMap<String, String>(), null);
        }

        private String mimeOf(String path) {
            String p = path.toLowerCase();
            if (p.endsWith(".html") || p.endsWith(".htm")) return "text/html";
            if (p.endsWith(".js")) return "application/javascript";
            if (p.endsWith(".json")) return "application/json";
            if (p.endsWith(".css")) return "text/css";
            if (p.endsWith(".svg")) return "image/svg+xml";
            if (p.endsWith(".png")) return "image/png";
            if (p.endsWith(".jpg") || p.endsWith(".jpeg")) return "image/jpeg";
            if (p.endsWith(".webp")) return "image/webp";
            if (p.endsWith(".woff2")) return "font/woff2";
            return "application/octet-stream";
        }
    }
}
