package store.ninavpn.vpn

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.VpnService
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Log
import java.lang.ref.WeakReference

/**
 * Tracks the underlying (non-VPN) default network for [VpnService.Builder.setUnderlyingNetworks]
 * and refreshes it while the tunnel is up (Wi‑Fi blips otherwise stall Reality).
 *
 * Also binds this process to that network so app API calls (login, /me) never traverse a
 * half-dead tunnel — critical on MIUI where addDisallowedApplication alone is unreliable.
 */
object DefaultNetworkMonitor {
  private const val TAG = "DefaultNetworkMonitor"

  private var connectivity: ConnectivityManager? = null
  private var callback: ConnectivityManager.NetworkCallback? = null
  private var vpnRef: WeakReference<VpnService>? = null
  private var appContext: Context? = null
  @Volatile
  var defaultNetwork: Network? = null
    private set
  private val mainHandler = Handler(Looper.getMainLooper())

  private val request: NetworkRequest =
    NetworkRequest.Builder()
      .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
      .addCapability(NetworkCapabilities.NET_CAPABILITY_NOT_RESTRICTED)
      .build()

  @Synchronized
  fun start(context: Context, vpn: VpnService? = null) {
    appContext = context.applicationContext
    if (vpn != null) vpnRef = WeakReference(vpn)
    if (callback != null) {
      applyUnderlying()
      return
    }
    val cm =
      context.applicationContext.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    connectivity = cm
    val cb =
      object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) {
          defaultNetwork = network
          applyUnderlying()
          Log.i(TAG, "underlying network available")
        }

        override fun onCapabilitiesChanged(network: Network, caps: NetworkCapabilities) {
          if (defaultNetwork == network) {
            defaultNetwork = network
            applyUnderlying()
          }
        }

        override fun onLost(network: Network) {
          if (defaultNetwork == network) {
            defaultNetwork = null
            // Pick a replacement immediately — otherwise bindProcessToNetwork keeps
            // pointing at a dead Network and all app HTTPS (support chat etc.) hangs.
            connectivity?.let { pickInitial(it) }
            applyUnderlying()
            Log.i(TAG, "underlying network lost")
          }
        }
      }
    callback = cb
    try {
      when {
        Build.VERSION.SDK_INT >= 31 -> {
          cm.registerBestMatchingNetworkCallback(request, cb, mainHandler)
        }
        Build.VERSION.SDK_INT >= 28 -> {
          cm.requestNetwork(request, cb, mainHandler)
        }
        Build.VERSION.SDK_INT >= 26 -> {
          cm.registerDefaultNetworkCallback(cb, mainHandler)
        }
        Build.VERSION.SDK_INT >= 24 -> {
          cm.registerDefaultNetworkCallback(cb)
        }
        else -> {
          @Suppress("DEPRECATION")
          cm.requestNetwork(request, cb)
        }
      }
    } catch (e: Exception) {
      Log.e(TAG, "register network callback failed, falling back", e)
      try {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
          cm.registerDefaultNetworkCallback(cb)
        }
      } catch (e2: Exception) {
        Log.e(TAG, "fallback registerDefaultNetworkCallback", e2)
      }
    }
    pickInitial(cm)
    applyUnderlying()
  }

  @Synchronized
  fun stop() {
    val ctx = appContext
    val cm = connectivity
    val cb = callback
    if (cm != null && cb != null) {
      try {
        cm.unregisterNetworkCallback(cb)
      } catch (_: Exception) {
      }
    }
    callback = null
    connectivity = null
    defaultNetwork = null
    vpnRef = null
    appContext = null
    if (ctx != null) unbindAppProcess(ctx)
  }

  private fun pickInitial(cm: ConnectivityManager) {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return
    val active = cm.activeNetwork
    val caps = active?.let { cm.getNetworkCapabilities(it) }
    defaultNetwork =
      if (active != null && caps != null && !caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN)) {
        active
      } else {
        cm.allNetworks.firstOrNull { n ->
          val c = cm.getNetworkCapabilities(n) ?: return@firstOrNull false
          c.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            !c.hasTransport(NetworkCapabilities.TRANSPORT_VPN)
        } ?: active
      }
  }

  private fun applyUnderlying() {
    val net = defaultNetwork
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP_MR1) {
      val vpn = vpnRef?.get()
      if (vpn != null) {
        try {
          vpn.setUnderlyingNetworks(if (net != null) arrayOf(net) else null)
        } catch (e: Exception) {
          Log.w(TAG, "setUnderlyingNetworks", e)
        }
      }
    }
    val ctx = appContext
    if (ctx != null) bindAppProcess(ctx)
  }

  /** Force app + Xray outbound sockets onto Wi‑Fi/cellular, not the TUN. */
  fun bindAppProcess(context: Context) {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return
    val cm =
      context.applicationContext.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
        ?: return
    val net = defaultNetwork
    if (net == null) {
      // Critical: do not leave a stale bind when the tracked network disappeared.
      unbindAppProcess(context)
      return
    }
    try {
      cm.bindProcessToNetwork(net)
      Log.i(TAG, "bound process to underlying network")
    } catch (e: Exception) {
      Log.w(TAG, "bindProcessToNetwork", e)
      unbindAppProcess(context)
    }
  }

  fun unbindAppProcess(context: Context) {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return
    val cm =
      context.applicationContext.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
        ?: return
    try {
      cm.bindProcessToNetwork(null)
      Log.i(TAG, "unbound process from network")
    } catch (_: Exception) {
    }
  }

  /**
   * Call before cabinet API requests.
   *
   * IMPORTANT: only *clear* process→network bind. Never re-bind here.
   * The VPN builder already uses addDisallowedApplication(this package), so
   * cabinet HTTPS should use the system default network. Re-binding to an
   * underlay on MIUI caused asymmetric hangs: server got POST (and TG notify)
   * while the app never received the HTTP 200 (support chat timeouts).
   */
  @Synchronized
  fun refreshForApi(context: Context) {
    val ctx = context.applicationContext
    appContext = ctx
    unbindAppProcess(ctx)
  }
}
