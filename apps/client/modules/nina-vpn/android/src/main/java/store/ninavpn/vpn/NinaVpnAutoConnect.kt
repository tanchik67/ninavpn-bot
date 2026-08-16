package store.ninavpn.vpn

import android.content.Context
import android.content.Intent
import android.net.VpnService
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Log

/**
 * Auto-connect on a real activity entry (cold start or return from recents).
 * JS AppState is unreliable on MIUI when the app stays in Recents.
 */
object NinaVpnAutoConnect {
  private const val TAG = "NinaVpnAuto"
  private val handler = Handler(Looper.getMainLooper())

  /** True until the next resume that should try to connect. Cold start counts. */
  @Volatile
  private var away = true

  private var awayRunnable: Runnable? = null
  private var resumeRunnable: Runnable? = null
  @Volatile
  private var lastStartAt = 0L

  fun onUserLeave() {
    resumeRunnable?.let { handler.removeCallbacks(it) }
    resumeRunnable = null
    awayRunnable?.let { handler.removeCallbacks(it) }
    awayRunnable = null
    away = true
    Log.i(TAG, "user leave → away=true")
  }

  fun onPause() {
    resumeRunnable?.let { handler.removeCallbacks(it) }
    resumeRunnable = null
    if (awayRunnable != null) return
    val r = Runnable {
      awayRunnable = null
      away = true
      Log.i(TAG, "away=true")
    }
    awayRunnable = r
    handler.postDelayed(r, 180)
  }

  fun onResume(ctx: Context) {
    awayRunnable?.let { handler.removeCallbacks(it) }
    awayRunnable = null
    resumeRunnable?.let { handler.removeCallbacks(it) }
    if (!away) {
      Log.i(TAG, "resume ignored (still foreground)")
      return
    }
    val app = ctx.applicationContext
    val r = Runnable {
      resumeRunnable = null
      if (!away) return@Runnable
      away = false
      tryStart(app)
    }
    resumeRunnable = r
    handler.postDelayed(r, 220)
  }

  fun tryStart(ctx: Context) {
    val prefs = ctx.getSharedPreferences(NinaVpnService.PREFS, Context.MODE_PRIVATE)
    val autoOn = NinaVpnService.autoConnectPref || prefs.getBoolean("autoConnect", false)
    if (!autoOn) {
      Log.i(TAG, "skip: autoConnect off")
      return
    }
    startFromLast(ctx)
  }

  /** Connect using the last node. Used by auto-connect and the Quick Settings tile. */
  fun startFromLast(ctx: Context): Boolean {
    val now = System.currentTimeMillis()
    if (now - lastStartAt < 800) {
      Log.i(TAG, "skip: debounce")
      return false
    }
    val prefs = ctx.getSharedPreferences(NinaVpnService.PREFS, Context.MODE_PRIVATE)
    val allowed = NinaVpnService.tunnelAllowed || prefs.getBoolean("tunnelAllowed", false)
    if (!allowed) {
      Log.i(TAG, "skip: no active subscription")
      return false
    }
    val st = NinaVpnService.currentStatus
    if (st == "connected" || st == "connecting") {
      Log.i(TAG, "skip: status=$st")
      return true
    }
    val uri = prefs.getString("lastUri", "") ?: ""
    if (uri.isBlank()) {
      Log.i(TAG, "skip: no lastUri")
      return false
    }
    if (VpnService.prepare(ctx) != null) {
      Log.i(TAG, "skip: vpn permission")
      return false
    }
    lastStartAt = now
    val nodeId = prefs.getString("lastNodeId", "") ?: ""
    Log.i(TAG, "start uriLen=${uri.length} node=$nodeId")
    NinaVpnService.currentStatus = "connecting"
    NinaVpnService.statusListener?.invoke("connecting")
    NinaVpnQs.notify(ctx)
    val i = Intent(ctx, NinaVpnService::class.java).apply {
      action = NinaVpnService.ACTION_CONNECT
      putExtra(NinaVpnService.EXTRA_URI, uri)
      putExtra(NinaVpnService.EXTRA_NODE_ID, nodeId)
    }
    return try {
      if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
        ctx.startForegroundService(i)
      } else {
        ctx.startService(i)
      }
      true
    } catch (e: Exception) {
      Log.e(TAG, "start failed: ${e.message}", e)
      NinaVpnService.currentStatus = "disconnected"
      NinaVpnService.statusListener?.invoke("disconnected")
      NinaVpnQs.notify(ctx)
      false
    }
  }
}
