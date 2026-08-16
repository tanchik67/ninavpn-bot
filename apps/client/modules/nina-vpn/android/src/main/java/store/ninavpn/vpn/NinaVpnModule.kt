package store.ninavpn.vpn

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.VpnService
import android.os.Build
import expo.modules.kotlin.Promise
import expo.modules.kotlin.exception.Exceptions
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import java.net.InetSocketAddress
import java.net.Socket

private const val PREPARE_REQ = 0x4E56 // 'NV'

class NinaVpnModule : Module() {
  private val context
    get() = appContext.reactContext ?: throw Exceptions.ReactContextLost()

  @Volatile
  private var preparePromise: Promise? = null

  override fun definition() = ModuleDefinition {
    Name("NinaVpn")
    Events("NinaVpnStatus")

    OnCreate {
      NinaVpnService.statusListener = { status ->
        sendEvent("NinaVpnStatus", mapOf("status" to status))
      }
    }

    OnUserLeavesActivity {
      NinaVpnAutoConnect.onUserLeave()
    }

    OnActivityEntersBackground {
      NinaVpnAutoConnect.onPause()
    }

    OnActivityEntersForeground {
      val act = appContext.currentActivity ?: appContext.reactContext
      if (act != null) NinaVpnAutoConnect.onResume(act)
    }

    OnActivityResult { _, payload ->
      if (payload.requestCode != PREPARE_REQ) return@OnActivityResult
      val p = preparePromise
      preparePromise = null
      val granted = payload.resultCode == Activity.RESULT_OK
      p?.resolve(granted)
    }

    AsyncFunction("isSupported") {
      Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP
    }

    AsyncFunction("prepare") { promise: Promise ->
      val act = appContext.currentActivity
      if (act == null) {
        promise.resolve(false)
        return@AsyncFunction
      }
      // Cancel a previous pending prepare (activity recreation / double-tap)
      preparePromise?.resolve(false)
      preparePromise = null
      val intent = VpnService.prepare(act)
      if (intent != null) {
        preparePromise = promise
        act.startActivityForResult(intent, PREPARE_REQ)
      } else {
        promise.resolve(true)
      }
    }

    AsyncFunction("connect") { uri: String, nodeId: String, promise: Promise ->
      try {
        val prefs = context.getSharedPreferences(NinaVpnService.PREFS, Context.MODE_PRIVATE)
        val allowed =
          NinaVpnService.tunnelAllowed || prefs.getBoolean("tunnelAllowed", false)
        if (!allowed) {
          sendEvent("NinaVpnStatus", mapOf("status" to "disconnected"))
          promise.reject("VPN_NO_SUB", "vpn_no_subscription", null)
          return@AsyncFunction
        }
        sendEvent("NinaVpnStatus", mapOf("status" to "connecting"))
        val prepared = VpnService.prepare(context)
        if (prepared != null) {
          sendEvent("NinaVpnStatus", mapOf("status" to "disconnected"))
          promise.reject("VPN_PERMISSION", "vpn_permission_required", null)
          return@AsyncFunction
        }
        // Register before startService — connect can fail in <100ms on Xiaomi
        NinaVpnService.statusListener = { status ->
          sendEvent("NinaVpnStatus", mapOf("status" to status))
        }
        NinaVpnService.currentStatus = "connecting"
        val i = Intent(context, NinaVpnService::class.java).apply {
          action = NinaVpnService.ACTION_CONNECT
          putExtra(NinaVpnService.EXTRA_URI, uri)
          putExtra(NinaVpnService.EXTRA_NODE_ID, nodeId)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
          context.startForegroundService(i)
        } else {
          context.startService(i)
        }
        promise.resolve(null)
      } catch (e: Exception) {
        sendEvent("NinaVpnStatus", mapOf("status" to "disconnected"))
        promise.reject("VPN_CONNECT", e.message ?: "vpn_failed", e)
      }
    }

    AsyncFunction("requestQuickTile") {
      requestAddQuickTile()
    }

    AsyncFunction("disconnect") { promise: Promise ->
      try {
        // Stop core immediately — don't wait for the service intent on MIUI
        XrayBridge.stop()
      } catch (_: Exception) {
      }
      NinaVpnService.currentStatus = "disconnected"
      sendEvent("NinaVpnStatus", mapOf("status" to "disconnected"))
      NinaVpnQs.notify(context)
      try {
        val i = Intent(context, NinaVpnService::class.java).apply {
          action = NinaVpnService.ACTION_DISCONNECT
        }
        context.startService(i)
      } catch (_: Exception) {
      }
      promise.resolve(null)
    }

    AsyncFunction("getStatus") {
      NinaVpnService.currentStatus
    }

    /** Fix stale bindProcessToNetwork so HTTPS works after VPN off / Wi‑Fi blips. */
    AsyncFunction("ensureNetwork") {
      DefaultNetworkMonitor.refreshForApi(context)
      null
    }

    /** TCP connect RTT to a VPN node. HTTP/XHR to Reality ports often returns nothing. */
    AsyncFunction("tcpPingMs") { host: String, port: Int, timeoutMs: Int ->
      val wait = timeoutMs.coerceIn(300, 8000)
      val t0 = System.nanoTime()
      try {
        Socket().use { socket ->
          socket.connect(InetSocketAddress(host, port), wait)
        }
        ((System.nanoTime() - t0) / 1_000_000L).toInt().coerceAtLeast(1)
      } catch (_: Exception) {
        -1
      }
    }

    AsyncFunction("setOptions") { killSwitch: Boolean, lanAccess: Boolean, autoConnect: Boolean, tunnelAllowed: Boolean ->
      NinaVpnService.autoConnectPref = autoConnect
      NinaVpnService.tunnelAllowed = tunnelAllowed
      context.getSharedPreferences(NinaVpnService.PREFS, Context.MODE_PRIVATE)
        .edit()
        .putBoolean("killSwitch", killSwitch)
        .putBoolean("lanAccess", lanAccess)
        .putBoolean("autoConnect", autoConnect)
        .putBoolean("tunnelAllowed", tunnelAllowed)
        .commit()
      true
    }

    AsyncFunction("clearSession") { promise: Promise ->
      try {
        XrayBridge.stop()
      } catch (_: Exception) {
      }
      NinaVpnService.autoConnectPref = false
      NinaVpnService.tunnelAllowed = false
      NinaVpnService.currentStatus = "disconnected"
      sendEvent("NinaVpnStatus", mapOf("status" to "disconnected"))
      try {
        context.getSharedPreferences(NinaVpnService.PREFS, Context.MODE_PRIVATE)
          .edit()
          .putBoolean("autoConnect", false)
          .putBoolean("tunnelAllowed", false)
          .putString("lastUri", "")
          .putString("lastNodeId", "")
          .commit()
      } catch (_: Exception) {
      }
      try {
        val i = Intent(context, NinaVpnService::class.java).apply {
          action = NinaVpnService.ACTION_DISCONNECT
        }
        context.startService(i)
      } catch (_: Exception) {
      }
      promise.resolve(null)
    }

    AsyncFunction("reconnect") { promise: Promise ->
      try {
        val prefs = context.getSharedPreferences(NinaVpnService.PREFS, Context.MODE_PRIVATE)
        val allowed =
          NinaVpnService.tunnelAllowed || prefs.getBoolean("tunnelAllowed", false)
        if (!allowed) {
          promise.resolve(false)
          return@AsyncFunction
        }
        val uri = prefs.getString("lastUri", "") ?: ""
        if (uri.isBlank()) {
          promise.resolve(false)
          return@AsyncFunction
        }
        val nodeId = prefs.getString("lastNodeId", "") ?: ""
        val prepared = VpnService.prepare(context)
        if (prepared != null) {
          promise.resolve(false)
          return@AsyncFunction
        }
        NinaVpnService.statusListener = { status ->
          sendEvent("NinaVpnStatus", mapOf("status" to status))
        }
        val i = Intent(context, NinaVpnService::class.java).apply {
          action = NinaVpnService.ACTION_CONNECT
          putExtra(NinaVpnService.EXTRA_URI, uri)
          putExtra(NinaVpnService.EXTRA_NODE_ID, nodeId)
          putExtra(NinaVpnService.EXTRA_KILL_SWITCH, prefs.getBoolean("killSwitch", true))
          putExtra(NinaVpnService.EXTRA_LAN_ACCESS, prefs.getBoolean("lanAccess", false))
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
          context.startForegroundService(i)
        } else {
          context.startService(i)
        }
        promise.resolve(true)
      } catch (e: Exception) {
        promise.reject("VPN_RECONNECT", e.message ?: "vpn_failed", e)
      }
    }
  }

  private fun requestAddQuickTile(): Boolean {
    if (Build.VERSION.SDK_INT < 33) return false
    val ctx = try {
      context
    } catch (_: Exception) {
      return false
    }
    val prefs = ctx.getSharedPreferences(NinaVpnService.PREFS, Context.MODE_PRIVATE)
    if (prefs.getBoolean("qsTileAsked", false)) return false
    val act = appContext.currentActivity ?: return false
    return try {
      val sm = act.getSystemService(android.app.StatusBarManager::class.java) ?: return false
      prefs.edit().putBoolean("qsTileAsked", true).apply()
      sm.requestAddTileService(
        android.content.ComponentName(ctx, NinaVpnTileService::class.java),
        ctx.getString(R.string.qs_tile_label),
        android.graphics.drawable.Icon.createWithResource(ctx, R.drawable.ic_qs_nv),
        ctx.mainExecutor,
      ) { _ -> }
      true
    } catch (_: Exception) {
      false
    }
  }
}
