package store.ninavpn.vpn

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.VpnService
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat

/**
 * System VPN service for NinaVPN — permission + foreground + Xray data plane.
 */
class NinaVpnService : VpnService() {
  companion object {
    const val ACTION_CONNECT = "store.ninavpn.vpn.CONNECT"
    const val ACTION_DISCONNECT = "store.ninavpn.vpn.DISCONNECT"
    const val EXTRA_URI = "uri"
    const val EXTRA_NODE_ID = "nodeId"
    const val EXTRA_KILL_SWITCH = "killSwitch"
    const val EXTRA_LAN_ACCESS = "lanAccess"
    const val PREFS = "ninavpn"
    const val CHANNEL_ID = "ninavpn"
    const val NOTIF_ID = 42

    @Volatile
    var currentStatus: String = "disconnected"

    @Volatile
    var autoConnectPref: Boolean = false

    @Volatile
    var tunnelAllowed: Boolean = false

    var statusListener: ((String) -> Unit)? = null

    private const val TAG = "NinaVpnService"
  }

  override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
    when (intent?.action) {
      ACTION_DISCONNECT -> {
        tearDown()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
        return START_NOT_STICKY
      }
      ACTION_CONNECT -> {
        val prefs = getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val allowed = tunnelAllowed || prefs.getBoolean("tunnelAllowed", false)
        if (!allowed) {
          Log.i(TAG, "ACTION_CONNECT denied: no subscription")
          tearDown()
          stopForeground(STOP_FOREGROUND_REMOVE)
          stopSelf()
          return START_NOT_STICKY
        }
        val uri = intent.getStringExtra(EXTRA_URI) ?: ""
        val killSwitch = intent.getBooleanExtra(
          EXTRA_KILL_SWITCH,
          prefs.getBoolean("killSwitch", true),
        )
        val lanAccess = intent.getBooleanExtra(
          EXTRA_LAN_ACCESS,
          prefs.getBoolean("lanAccess", false),
        )
        if (uri.isNotBlank()) {
          prefs.edit()
            .putString("lastUri", uri)
            .putString("lastNodeId", intent.getStringExtra(EXTRA_NODE_ID) ?: "")
            .apply()
        }
        Log.e(TAG, "ACTION_CONNECT uriLen=${uri.length} kill=$killSwitch lan=$lanAccess")
        startForeground(NOTIF_ID, buildNotification("Connecting…"))
        setStatus("connecting")
        try {
          if (uri.isBlank()) throw IllegalArgumentException("empty_uri")
          val started = XrayBridge.start(uri, this, killSwitch, lanAccess)
          if (started) {
            setStatus("connected")
            startForeground(NOTIF_ID, buildNotification("Connected"))
            Log.e(TAG, "connected ok")
          } else {
            Log.e(TAG, "XrayBridge.start returned false")
            setStatus("disconnected")
            tearDown()
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
          }
        } catch (e: Exception) {
          Log.e(TAG, "connect failed: ${e.message}", e)
          setStatus("disconnected")
          tearDown()
          stopForeground(STOP_FOREGROUND_REMOVE)
          stopSelf()
        }
      }
    }
    return START_STICKY
  }

  private fun tearDown() {
    try {
      XrayBridge.stop()
    } catch (_: Exception) {
    }
    setStatus("disconnected")
  }

  private fun setStatus(s: String) {
    currentStatus = s
    statusListener?.invoke(s)
    NinaVpnQs.notify(this)
  }

  private fun buildNotification(text: String): Notification {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
      val mgr = getSystemService(NotificationManager::class.java)
      mgr?.createNotificationChannel(
        NotificationChannel(CHANNEL_ID, "NinaVPN", NotificationManager.IMPORTANCE_LOW)
      )
    }
    val launch = packageManager.getLaunchIntentForPackage(packageName)
    val pi = PendingIntent.getActivity(
      this, 0, launch,
      PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
    )
    return NotificationCompat.Builder(this, CHANNEL_ID)
      .setContentTitle("NinaVPN")
      .setContentText(text)
      .setSmallIcon(android.R.drawable.ic_lock_lock)
      .setContentIntent(pi)
      .setOngoing(true)
      .build()
  }

  override fun onRevoke() {
    tearDown()
    stopSelf()
    super.onRevoke()
  }

  override fun onDestroy() {
    tearDown()
    super.onDestroy()
  }
}
