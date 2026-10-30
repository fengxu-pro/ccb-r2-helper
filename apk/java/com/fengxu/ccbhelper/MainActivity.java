package com.fengxu.ccbhelper;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {

    private static final String HOME_URL = "https://fengxu-pro.github.io/ccb-r2-helper/";
    private static final String HOME_HOST = "fengxu-pro.github.io";

    private WebView wv;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // 沉浸式：内容延伸到状态栏下方，状态栏红底
        if (Build.VERSION.SDK_INT >= 21) {
            Window w = getWindow();
            w.setStatusBarColor(Color.parseColor("#c8102e"));
            w.getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
        }

        wv = new WebView(this);
        WebSettings st = wv.getSettings();
        st.setJavaScriptEnabled(true);
        st.setDomStorageEnabled(true);          // localStorage 持久化（拉新数据还原）
        st.setDatabaseEnabled(true);
        st.setAllowFileAccess(false);
        st.setLoadWithOverviewMode(true);
        st.setUseWideViewPort(true);
        st.setSupportZoom(false);
        st.setMediaPlaybackRequiresUserGesture(false);
        st.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);

        wv.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return handleUrl(String.valueOf(request.getUrl()));
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return handleUrl(url);
            }

            private boolean handleUrl(String url) {
                Uri u = Uri.parse(url);
                if (HOME_HOST.equals(u.getHost())) {
                    return false; // 自己的站点，WebView 内打开（含 OTA 跳转）
                }
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, u)); // 外部链接（建行官网等）交给浏览器
                } catch (Exception ignored) {
                }
                return true;
            }
        });

        setContentView(wv);
        if (savedInstanceState == null) {
            wv.loadUrl(HOME_URL);
        } else {
            wv.restoreState(savedInstanceState);
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        if (wv != null) wv.saveState(outState);
    }

    @Override
    public void onBackPressed() {
        if (wv != null && wv.canGoBack()) wv.goBack();
        else super.onBackPressed();
    }
}
