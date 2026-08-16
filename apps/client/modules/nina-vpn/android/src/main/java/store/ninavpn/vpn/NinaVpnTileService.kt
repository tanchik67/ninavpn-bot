package store.ninavpn.vpn

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.graphics.drawable.Icon
import android.net.VpnService
import android.os.Build
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService

/**
 * Quick Settings tile — toggle NinaVPN from the shade, like iOS Control Center.
 */
class NinaVpnTileService : TileService() {
  override fun onStartListening() {
    super.onStartListening()
    refresh()
  }

  override fun onClick() {
    // unlockAndRun collapses MIUI Control Center onto the launcher even
    // when the phone is already unlocked. Only use it on the lock screen.
    if (isLocked) {
      unlockAndRun { handleClick() }
    } else {
      handleClick()
    }
  }

  private fun handleClick() {
    val st = NinaVpnService.currentStatus
    if (st == "connected" || st == "connecting") {
      refresh("disconnected")
      disconnect()
      return
    }
    val prefs = getSharedPreferences(NinaVpnService.PREFS, Context.MODE_PRIVATE)
    val allowed =
      NinaVpnService.tunnelAllowed || prefs.getBoolean("tunnelAllowed", false)
    val uri = prefs.getString("lastUri", "") ?: ""
    if (!allowed || uri.isBlank() || VpnService.prepare(this) != null) {
      openApp()
      return
    }
    refresh("connecting")
    NinaVpnAutoConnect.startFromLast(applicationContext)
  }

  private fun disconnect() {
    try {
      XrayBridge.stop()
    } catch (_: Exception) {
    }
    NinaVpnService.currentStatus = "disconnected"
    NinaVpnService.statusListener?.invoke("disconnected")
    try {
      startService(
        Intent(this, NinaVpnService::class.java).apply {
          action = NinaVpnService.ACTION_DISCONNECT
        }
      )
    } catch (_: Exception) {
    }
    NinaVpnQs.notify(this)
  }

  private fun openApp() {
    val launch = packageManager.getLaunchIntentForPackage(packageName) ?: return
    launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    try {
      if (Build.VERSION.SDK_INT >= 34) {
        val pi =
          PendingIntent.getActivity(
            this,
            0,
            launch,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
          )
        startActivityAndCollapse(pi)
      } else {
        @Suppress("DEPRECATION")
        startActivityAndCollapse(launch)
      }
    } catch (_: Exception) {
      try {
        startActivity(launch)
      } catch (_: Exception) {
      }
    }
  }

  private fun refresh(statusOverride: String? = null) {
    val tile = qsTile ?: return
    val st = statusOverride ?: NinaVpnService.currentStatus
    tile.icon = Icon.createWithResource(this, R.drawable.ic_qs_nv)
    tile.label = getString(R.string.qs_tile_label)
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
      tile.subtitle =
        when (st) {
          "connected" -> "On"
          "connecting" -> "…"
          else -> "Off"
        }
    }
    tile.state =
      when (st) {
        "connected", "connecting" -> Tile.STATE_ACTIVE
        else -> Tile.STATE_INACTIVE
      }
    tile.updateTile()
  }
}
