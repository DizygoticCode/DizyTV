package dev.dizygotic.dizytv

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import java.io.ByteArrayInputStream

/**
 * Isolated, user-initiated preview of permitted Matchday webpages.
 * No JavaScript bridge, no file access, no HTTP/mixed content, no browser
 * takeover/popup or third-party cookies. The external browser is an explicit
 * fallback where a site's video player is incompatible with WebView.
 */
class MatchdayWebActivity:Activity() {
    private lateinit var browser:WebView
    private lateinit var container:FrameLayout
    private lateinit var original:String
    private var fullScreenView:View?=null
    private var fullScreenCallback:WebChromeClient.CustomViewCallback?=null

    override fun onCreate(savedInstanceState:Bundle?) {
        super.onCreate(savedInstanceState)
        original=runCatching {
            MatchdayLinkPolicy.validateSource(intent.getStringExtra("matchday_url") ?: "")
        }.getOrElse { finish(); return }
        window.statusBarColor=Color.rgb(15,22,18)
        val root=LinearLayout(this).apply {
            orientation=LinearLayout.VERTICAL
            setBackgroundColor(Color.rgb(15,22,18))
        }
        val toolbar=LinearLayout(this).apply { orientation=LinearLayout.HORIZONTAL }
        val close=Button(this).apply { text="Close";setOnClickListener { finish() } }
        toolbar.addView(close)
        val external=Button(this).apply {
            text="Open in browser"
            setOnClickListener {
                startActivity(Intent(Intent.ACTION_VIEW,Uri.parse(original)))
            }
        }
        toolbar.addView(external)
        root.addView(toolbar)
        val notice=TextView(this).apply {
            text="Unverified third-party webpage. No login, subscriptions or playback rights are verified. If video fails, use Open in browser."
            setTextColor(Color.WHITE)
            setPadding(14,10,14,10)
        }
        root.addView(notice)
        container=FrameLayout(this)
        browser=WebView(this)
        val settings=browser.settings
        settings.javaScriptEnabled=true  // Necessary for some authorised website players.
        settings.domStorageEnabled=false
        settings.allowFileAccess=false
        settings.allowContentAccess=false
        settings.javaScriptCanOpenWindowsAutomatically=false
        settings.setSupportMultipleWindows(false)
        settings.mixedContentMode=WebSettings.MIXED_CONTENT_NEVER_ALLOW
        settings.mediaPlaybackRequiresUserGesture=true
        settings.setGeolocationEnabled(false)
        settings.safeBrowsingEnabled=true
        CookieManager.getInstance().setAcceptThirdPartyCookies(browser,false)
        browser.webViewClient=object:WebViewClient() {
            override fun shouldOverrideUrlLoading(view:WebView,request:WebResourceRequest):Boolean {
                if (!request.isForMainFrame) return false
                val next=request.url.toString()
                if (MatchdayLinkPolicy.sameSiteNavigation(original,next)) return false
                AlertDialog.Builder(this@MatchdayWebActivity)
                    .setTitle("External webpage blocked")
                    .setMessage("This embedded player tried to open another website. Use Open in browser if you trust the original source.")
                    .setPositiveButton("OK",null).show()
                return true
            }
            override fun shouldInterceptRequest(view:WebView,request:WebResourceRequest):WebResourceResponse? {
                if (MatchdayLinkPolicy.allowResource(request.url.toString())) return null
                // Block local network, cleartext, content/file and arbitrary schemes.
                return WebResourceResponse("text/plain","UTF-8",ByteArrayInputStream(ByteArray(0)))
            }
        }
        browser.webChromeClient=object:WebChromeClient() {
            override fun onPermissionRequest(request:PermissionRequest) { request.deny() }
            override fun onShowCustomView(view:View,callback:CustomViewCallback) {
                if (fullScreenView!=null) { callback.onCustomViewHidden();return }
                fullScreenView=view
                fullScreenCallback=callback
                container.addView(view,FrameLayout.LayoutParams(-1,-1))
                browser.visibility=View.GONE
            }
            override fun onHideCustomView() { exitVideoFullscreen() }
        }
        browser.setDownloadListener { _,_,_,_,_ ->
            runOnUiThread {
                AlertDialog.Builder(this).setMessage("Downloads are not supported inside Matchday.")
                    .setPositiveButton("OK",null).show()
            }
        }
        container.addView(browser,FrameLayout.LayoutParams(-1,-1))
        root.addView(container,LinearLayout.LayoutParams(-1,0,1f))
        setContentView(root)
        browser.loadUrl(original)
    }

    private fun exitVideoFullscreen() {
        fullScreenView?.let { container.removeView(it) }
        fullScreenView=null
        fullScreenCallback?.onCustomViewHidden()
        fullScreenCallback=null
        if (::browser.isInitialized) browser.visibility=View.VISIBLE
    }

    @Deprecated("Android system back handling can be migrated independently.")
    override fun onBackPressed() {
        if (fullScreenView!=null) exitVideoFullscreen()
        else if (::browser.isInitialized && browser.canGoBack()) browser.goBack()
        else finish()
    }

    override fun onDestroy() {
        if (::browser.isInitialized) {
            exitVideoFullscreen()
            browser.stopLoading()
            browser.loadUrl("about:blank")
            browser.clearHistory()
            browser.clearCache(true)
            (browser.parent as? ViewGroup)?.removeView(browser)
            browser.destroy()
            // Matchday is DizyTV's only WebView; do not keep browsing cookies.
            CookieManager.getInstance().removeAllCookies(null)
        }
        super.onDestroy()
    }
}
