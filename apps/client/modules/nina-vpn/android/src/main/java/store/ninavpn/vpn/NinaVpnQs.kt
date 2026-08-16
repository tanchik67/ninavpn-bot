package store.ninavpn.vpn

import android.content.ComponentName
import android.content.Context
import android.os.Build
import android.service.quicksettings.TileService

object NinaVpnQs {
  fun notify(ctx: Context) {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.N) return
    try {
      TileService.requestListeningState(
        ctx.applicationContext,
        ComponentName(ctx.applicationContext, NinaVpnTileService::class.java),
      )
    } catch (_: Exception) {
    }
  }
}
