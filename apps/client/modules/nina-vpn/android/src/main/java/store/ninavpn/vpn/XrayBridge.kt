package store.ninavpn.vpn

import android.content.Context
import android.net.VpnService
import android.os.Build
import android.os.ParcelFileDescriptor
import android.util.Log
import go.Seq
import libv2ray.CoreCallbackHandler
import libv2ray.CoreController
import libv2ray.Libv2ray
import java.io.File

/**
 * Bridges NinaVPN VpnService ↔ AndroidLibXrayLite (Xray-core).
 *
 * TUN is established in Kotlin; the fd is passed to [CoreController.startLoop] via
 * env `xray.tun.fd`. Own package is disallowed from the VPN so core outbound sockets
 * do not loop back into the tunnel (no protect callback in current libv2ray).
 */
object XrayBridge {
  private const val TAG = "XrayBridge"
  private const val TUN_ADDR = "10.10.14.1"
  private const val TUN_PREFIX = 30
  private const val TUN_MTU = 1280

  @Volatile
  private var setupDone = false

  @Volatile
  private var controller: CoreController? = null

  @Volatile
  private var tunPfd: ParcelFileDescriptor? = null

  @JvmStatic
  @Synchronized
  fun start(uri: String, vpn: VpnService, killSwitch: Boolean = true, lanAccess: Boolean = false): Boolean {
    stopLocked()
    ensureSetup(vpn.applicationContext)
    DefaultNetworkMonitor.start(vpn.applicationContext, vpn)

    val config = VlessConfigBuilder.fromShareUri(uri, lanAccess)
    Log.e(TAG, "config bytes=${config.length} uriHead=${uri.take(120)} kill=$killSwitch lan=$lanAccess")
    Log.e(TAG, "config json=${config.take(1600)}")
    Log.i(TAG, "libv2ray ${Libv2ray.checkVersionX()}")

    val pfd = establishTun(vpn, killSwitch) ?: run {
      Log.e(TAG, "TUN establish failed")
      return false
    }
    tunPfd = pfd

    val core = Libv2ray.newCoreController(object : CoreCallbackHandler {
      override fun startup(): Long = 0
      override fun shutdown(): Long = 0
      override fun onEmitStatus(l: Long, s: String?): Long {
        if (!s.isNullOrBlank()) Log.i(TAG, "status[$l]: $s")
        return 0
      }
    })

    try {
      core.startLoop(config, pfd.fd)
    } catch (e: Exception) {
      Log.e(TAG, "startLoop failed: ${e.message}", e)
      stopLocked()
      return false
    }

    if (!core.isRunning) {
      Log.e(TAG, "core reported not running after startLoop")
      stopLocked()
      return false
    }

    controller = core
    Log.i(TAG, "Xray core started tunFd=${pfd.fd}")
    return true
  }

  @JvmStatic
  @Synchronized
  fun stop() {
    stopLocked()
  }

  private fun stopLocked() {
    try {
      controller?.stopLoop()
    } catch (e: Exception) {
      Log.w(TAG, "stopLoop", e)
    }
    controller = null
    try {
      tunPfd?.close()
    } catch (_: Exception) {
    }
    tunPfd = null
    DefaultNetworkMonitor.stop()
  }

  private fun ensureSetup(ctx: Context) {
    if (setupDone) return
    Seq.setContext(ctx.applicationContext)
    val assets = File(ctx.filesDir, "xray").apply { mkdirs() }
    Libv2ray.initCoreEnv(assets.absolutePath, "")
    setupDone = true
    Log.i(TAG, "libv2ray setup done version=${Libv2ray.checkVersionX()}")
  }

  private fun establishTun(vpn: VpnService, killSwitch: Boolean): ParcelFileDescriptor? {
    if (VpnService.prepare(vpn) != null) {
      throw IllegalStateException("vpn_permission_required")
    }

    val builder = vpn.Builder()
      .setSession("NinaVPN")
      .setMtu(TUN_MTU)
      .addAddress(TUN_ADDR, TUN_PREFIX)
      .addRoute("0.0.0.0", 0)
      .addDnsServer("1.1.1.1")
      .addDnsServer("8.8.8.8")

    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
      builder.setMetered(false)
      // Kill switch: drop packets if the tunnel isn't reading them.
      try {
        builder.setBlocking(killSwitch)
      } catch (e: Exception) {
        Log.w(TAG, "setBlocking", e)
      }
    }

    // Without kill switch, apps may skip a broken tunnel. With it, stay inside.
    if (!killSwitch) {
      try {
        builder.allowBypass()
      } catch (e: Exception) {
        Log.w(TAG, "allowBypass", e)
      }
    }

    val underlying = DefaultNetworkMonitor.defaultNetwork
    if (underlying != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP_MR1) {
      try {
        builder.setUnderlyingNetworks(arrayOf(underlying))
      } catch (e: Exception) {
        Log.w(TAG, "setUnderlyingNetworks", e)
      }
    }

    try {
      builder.addDisallowedApplication(vpn.packageName)
    } catch (e: Exception) {
      Log.w(TAG, "addDisallowedApplication", e)
    }

    return try {
      val pfd = builder.establish()
      if (pfd == null) {
        Log.e(TAG, "builder.establish() returned null")
      } else {
        Log.i(TAG, "TUN established fd=${pfd.fd}")
        DefaultNetworkMonitor.bindAppProcess(vpn.applicationContext)
      }
      pfd
    } catch (e: Exception) {
      Log.e(TAG, "establish TUN", e)
      null
    }
  }
}
