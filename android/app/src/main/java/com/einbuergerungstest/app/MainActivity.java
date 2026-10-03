package com.einbuergerungstest.app;

import android.app.Activity;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.view.DisplayCutout;
import android.view.View;
import android.view.ViewTreeObserver;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
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

    /** The page's own background, so the inset padding matches it. */
    private static final int PAGE_BACKGROUND = Color.parseColor("#f4f5f7");

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
        // The page is a light grey; painting the WebView the same colour means
        // the inset padding above and below it does not show as a seam.
        webView.setBackgroundColor(PAGE_BACKGROUND);

        setContentView(webView);
        applyEdgeToEdgeInsets(webView);

        if (savedInstanceState != null) {
            webView.restoreState(savedInstanceState);
        } else {
            webView.loadUrl(ORIGIN + "/index.html");
        }
    }

    /**
     * Keeps the page clear of the status bar, the camera cutout and the
     * navigation bar.
     *
     * <p><b>Why this is needed at all.</b> From Android 15 an app targeting
     * SDK 35 is drawn edge to edge whether it asks for it or not: the window
     * extends under the status bar and into the notch, and nothing is inset
     * automatically. Without this the first line of the page sits behind the
     * clock and the cutout. The same is made true deliberately on older
     * releases below, so one code path covers every version instead of the
     * layout shifting depending on the phone.
     *
     * <p>Insets are applied as <b>padding on the WebView</b> rather than by
     * leaving the system to inset the window, because padding keeps the page's
     * own background colour painted in the gap — the area beside the notch
     * looks like part of the app, not like a bar bolted on top of it.
     */
    private void applyEdgeToEdgeInsets(final WebView view) {
        Window window = getWindow();

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            Api30.edgeToEdge(window);
        } else {
            // The pre-Android-11 spelling of the same thing, plus dark status
            // bar icons so the clock stays readable on the light background.
            window.getDecorView().setSystemUiVisibility(
                    View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                            | View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
        }

        view.setOnApplyWindowInsetsListener(new View.OnApplyWindowInsetsListener() {
            @Override
            public WindowInsets onApplyWindowInsets(View v, WindowInsets insets) {
                // Deliberately ignores the insets handed to this view and reads
                // the window's own instead. An intermediate layout is free to
                // consume the system-window insets on the way down, in which
                // case the values arriving here are already zero — which is
                // exactly how the page ended up drawn under the status bar.
                // getRootWindowInsets() reports what the window actually has,
                // whatever happened in between.
                syncInsetsFromRoot();
                return insets;
            }
        });

        // Belt and braces: the listener above only runs when the insets are
        // dispatched, and the first dispatch can happen before the view is
        // attached. Re-checking on layout costs nothing (it only writes when a
        // value actually changed) and guarantees the padding is correct even
        // if no dispatch ever arrives.
        view.getViewTreeObserver().addOnGlobalLayoutListener(
                new ViewTreeObserver.OnGlobalLayoutListener() {
                    @Override
                    public void onGlobalLayout() {
                        syncInsetsFromRoot();
                    }
                });
        view.requestApplyInsets();
    }

    /**
     * Applies the window's status-bar, cutout and navigation-bar insets as
     * padding on the WebView.
     *
     * <p>Padding rather than a window inset, because padding keeps the page's
     * own background colour painted in the gap — the strip beside the camera
     * hole then reads as part of the app instead of a band bolted on top.
     */
    private void syncInsetsFromRoot() {
        if (webView == null) {
            return;
        }
        WindowInsets insets = webView.getRootWindowInsets();
        if (insets == null) {
            return;
        }

        int left, top, right, bottom;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            android.graphics.Insets bars = Api30.systemBarsAndCutout(insets);
            left = bars.left;
            top = bars.top;
            right = bars.right;
            bottom = bars.bottom;
        } else {
            left = insets.getSystemWindowInsetLeft();
            top = insets.getSystemWindowInsetTop();
            right = insets.getSystemWindowInsetRight();
            bottom = insets.getSystemWindowInsetBottom();
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                // On a notched phone the status bar inset does not always
                // cover the cutout itself, so take the larger of the two.
                DisplayCutout cutout = insets.getDisplayCutout();
                if (cutout != null) {
                    left = Math.max(left, cutout.getSafeInsetLeft());
                    top = Math.max(top, cutout.getSafeInsetTop());
                    right = Math.max(right, cutout.getSafeInsetRight());
                    bottom = Math.max(bottom, cutout.getSafeInsetBottom());
                }
            }
        }

        // Only write when something changed, so the layout listener above
        // cannot keep triggering itself.
        if (webView.getPaddingLeft() != left || webView.getPaddingTop() != top
                || webView.getPaddingRight() != right || webView.getPaddingBottom() != bottom) {
            webView.setPadding(left, top, right, bottom);
        }
    }

    /** Isolated so the API-30 types are only ever touched on API 30 and up. */
    private static class Api30 {
        static void edgeToEdge(Window window) {
            window.setDecorFitsSystemWindows(false);
            WindowInsetsController controller = window.getInsetsController();
            if (controller != null) {
                controller.setSystemBarsAppearance(
                        WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS,
                        WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS);
            }
        }

        static android.graphics.Insets systemBarsAndCutout(WindowInsets insets) {
            return insets.getInsets(
                    WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
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
