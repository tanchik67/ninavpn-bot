package store.ninavpn.vpn

import android.net.Uri
import org.json.JSONArray
import org.json.JSONObject
import java.net.URLDecoder

/**
 * Convert a share link (vless://…) into Xray-core JSON with TUN inbound.
 *
 * Home/ISP DPI often stalls Reality ClientHello — TLS fragment + Mux keep a small
 * set of outer TCP sessions alive. QUIC/UDP:443 is rejected so YouTube/Telegram
 * stay on TCP through the proxy (UDP over Reality is flaky on many networks).
 */
object VlessConfigBuilder {
  fun fromShareUri(raw: String, lanAccess: Boolean = false): String {
    val uri = stripHeavyQueryParams(raw.trim())
    when {
      uri.startsWith("vless://", ignoreCase = true) -> return buildVless(uri, lanAccess)
      uri.startsWith("{") && uri.contains("\"outbounds\"") -> return uri
      else -> throw IllegalArgumentException("unsupported_uri")
    }
  }

  private fun stripHeavyQueryParams(link: String): String {
    val q = link.indexOf('?')
    if (q < 0) return link
    val hash = link.indexOf('#', q)
    val head = link.substring(0, q)
    val query = if (hash >= 0) link.substring(q + 1, hash) else link.substring(q + 1)
    val frag = if (hash >= 0) link.substring(hash) else ""
    val kept = query.split('&').filter { part ->
      if (part.isEmpty()) return@filter false
      val key = part.substringBefore('=').lowercase()
      key !in setOf("pqv", "pqc", "mlkem", "pq") && part.length <= 800
    }
    return if (kept.isEmpty()) head + frag else head + "?" + kept.joinToString("&") + frag
  }

  private fun buildVless(link: String, lanAccess: Boolean): String {
    val parsed = Uri.parse(link)
    val userInfo = parsed.userInfo ?: throw IllegalArgumentException("vless_missing_uuid")
    val uuid = URLDecoder.decode(userInfo, "UTF-8")
    val host = parsed.host ?: throw IllegalArgumentException("vless_missing_host")
    val port = if (parsed.port > 0) parsed.port else 443

    fun q(key: String): String =
      parsed.getQueryParameter(key)?.let { URLDecoder.decode(it, "UTF-8") } ?: ""

    val security = q("security").ifBlank { "none" }
    val sni = q("sni").ifBlank { q("host") }.ifBlank { host }
    val fp = q("fp").ifBlank { "chrome" }
    val pbk = q("pbk")
    val sid = q("sid")
    val flow = q("flow")
    val network = q("type").ifBlank { "tcp" }
    val path = q("path")
    val serviceName = q("serviceName").ifBlank { q("service_name") }
    val alpn = q("alpn")
    val spx = q("spx")
    val encryption = q("encryption").ifBlank { "none" }
    val useVision = flow.contains("vision", ignoreCase = true)

    val user = JSONObject()
      .put("id", uuid)
      .put("encryption", encryption)
      .put("level", 8)
    if (flow.isNotBlank()) user.put("flow", flow)

    val outbound = JSONObject()
      .put("tag", "proxy")
      .put("protocol", "vless")
      .put(
        "settings",
        JSONObject().put(
          "vnext",
          JSONArray().put(
            JSONObject()
              .put("address", host)
              .put("port", port)
              .put("users", JSONArray().put(user)),
          ),
        ),
      )

    // Mux collapses many app streams into few Reality TCP sessions (DPI-friendly).
    // Vision flow cannot use mux concurrency > 0.
    if (!useVision) {
      outbound.put(
        "mux",
        JSONObject()
          .put("enabled", true)
          .put("concurrency", 8)
          .put("xudpConcurrency", 16)
          .put("xudpProxyUDP443", "reject"),
      )
    } else {
      outbound.put(
        "mux",
        JSONObject()
          .put("enabled", false)
          .put("concurrency", -1)
          .put("xudpProxyUDP443", "reject"),
      )
    }

    val stream = JSONObject().put("network", network)
    when (network) {
      "ws" -> {
        val ws = JSONObject()
        if (path.isNotBlank()) ws.put("path", path)
        val hostHeader = q("host")
        if (hostHeader.isNotBlank()) {
          ws.put("headers", JSONObject().put("Host", hostHeader))
        }
        stream.put("wsSettings", ws)
      }
      "grpc" -> {
        val grpc = JSONObject()
        if (serviceName.isNotBlank()) grpc.put("serviceName", serviceName)
        stream.put("grpcSettings", grpc)
      }
      "http", "h2" -> {
        val http = JSONObject()
        if (path.isNotBlank()) http.put("path", path)
        val hostHeader = q("host")
        if (hostHeader.isNotBlank()) {
          http.put("host", JSONArray().put(hostHeader))
        }
        stream.put("httpSettings", http)
      }
    }

    if (security == "reality" || security == "tls") {
      stream.put("security", security)
      val tls = JSONObject().put("serverName", sni)
      if (fp.isNotBlank()) tls.put("fingerprint", fp)
      if (alpn.isNotBlank()) {
        tls.put(
          "alpn",
          JSONArray(alpn.split(",").map { it.trim() }.filter { it.isNotEmpty() }),
        )
      }
      if (security == "reality") {
        if (pbk.isNotBlank()) tls.put("publicKey", pbk)
        if (sid.isNotBlank()) tls.put("shortId", sid)
        tls.put("spiderX", spx.ifBlank { "" })
        stream.put("realitySettings", tls)
      } else {
        stream.put("tlsSettings", tls)
      }
    }

    stream.put(
      "sockopt",
      JSONObject()
        .put("dialerProxy", "fragment")
        .put("tcpNoDelay", true)
        .put("tcpKeepAliveIdle", 45)
        .put("tcpKeepAliveInterval", 15),
    )
    outbound.put("streamSettings", stream)

    val fragmentOutbound = JSONObject()
      .put("tag", "fragment")
      .put("protocol", "freedom")
      .put(
        "settings",
        JSONObject()
          .put(
            "fragment",
            JSONObject()
              .put("packets", "tlshello")
              .put("length", "100-200")
              .put("interval", "1-5"),
          )
          .put("domainStrategy", "UseIPv4"),
      )
      .put(
        "streamSettings",
        JSONObject().put(
          "sockopt",
          JSONObject()
            .put("tcpNoDelay", true)
            .put("tcpKeepAliveIdle", 45)
            .put("tcpKeepAliveInterval", 15),
        ),
      )

    val privateIps = JSONArray()
      .put("0.0.0.0/8")
      .put("10.0.0.0/8")
      .put("127.0.0.0/8")
      .put("169.254.0.0/16")
      .put("172.16.0.0/12")
      .put("192.168.0.0/16")
      .put("224.0.0.0/4")
      .put("240.0.0.0/4")

    val routingRules = JSONArray()
      // Prefer TCP: YouTube/Telegram QUIC over Reality dies after ~30–60s on many ISPs
      .put(
        JSONObject()
          .put("type", "field")
          .put("network", "udp")
          .put("port", "443")
          .put("outboundTag", "block"),
      )
      .put(
        JSONObject()
          .put("type", "field")
          .put("port", "53")
          .put("outboundTag", "dns-out"),
      )
      .put(
        JSONObject()
          .put("type", "field")
          .put("inboundTag", JSONArray().put("dns-module"))
          .put("outboundTag", "proxy"),
      )

    if (lanAccess) {
      routingRules.put(
        JSONObject()
          .put("type", "field")
          .put("ip", privateIps)
          .put("outboundTag", "direct"),
      )
    }

    val root = JSONObject()
      .put("log", JSONObject().put("loglevel", "warning"))
      .put(
        "policy",
        JSONObject()
          .put(
            "levels",
            JSONObject().put(
              "8",
              JSONObject()
                .put("handshake", 8)
                .put("connIdle", 300)
                .put("uplinkOnly", 2)
                .put("downlinkOnly", 5),
            ),
          )
          .put(
            "system",
            JSONObject()
              .put("statsOutboundUplink", false)
              .put("statsOutboundDownlink", false),
          ),
      )
      .put(
        "inbounds",
        JSONArray().put(
          JSONObject()
            .put("tag", "tun")
            .put("protocol", "tun")
            .put(
              "settings",
              JSONObject()
                .put("name", "xray0")
                .put("mtu", 1280)
                .put("userLevel", 8),
            )
            .put(
              "sniffing",
              JSONObject()
                .put("enabled", true)
                .put("destOverride", JSONArray().put("http").put("tls").put("quic"))
                .put("routeOnly", true),
            ),
        ),
      )
      .put(
        "outbounds",
        JSONArray()
          .put(outbound)
          .put(fragmentOutbound)
          .put(
            JSONObject()
              .put("tag", "direct")
              .put("protocol", "freedom")
              .put("settings", JSONObject().put("domainStrategy", "UseIPv4")),
          )
          .put(JSONObject().put("tag", "block").put("protocol", "blackhole"))
          .put(JSONObject().put("tag", "dns-out").put("protocol", "dns")),
      )
      .put(
        "routing",
        JSONObject()
          .put("domainStrategy", "AsIs")
          .put("rules", routingRules),
      )
      .put(
        "dns",
        JSONObject()
          .put(
            "servers",
            JSONArray()
              .put("https://1.1.1.1/dns-query")
              .put("https://8.8.8.8/dns-query")
              .put("1.1.1.1"),
          )
          .put("queryStrategy", "UseIPv4")
          .put("disableCache", false)
          .put("tag", "dns-module"),
      )

    return root.toString()
  }
}
