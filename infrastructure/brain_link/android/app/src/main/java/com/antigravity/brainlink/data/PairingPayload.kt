package com.antigravity.brainlink.data

import android.net.Uri
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import org.json.JSONObject

@Serializable
data class PairingPayload(
    val serverUrl: String,
    val authToken: String,
    val deviceName: String = "PC Server",
    val pairedAt: Long = System.currentTimeMillis()
) {
    companion object {
        private val json = Json { ignoreUnknownKeys = true }

        fun parse(rawString: String): PairingPayload? {
            val trimmed = rawString.trim()

            // 1. Try parsing as JSON
            try {
                if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
                    val jsonObj = JSONObject(trimmed)
                    val url = when {
                        jsonObj.has("server_url") -> jsonObj.getString("server_url")
                        jsonObj.has("serverUrl") -> jsonObj.getString("serverUrl")
                        jsonObj.has("ip") -> {
                            val ip = jsonObj.getString("ip")
                            val port = if (jsonObj.has("port")) jsonObj.getInt("port") else 8000
                            "http://$ip:$port"
                        }
                        else -> null
                    }

                    val token = when {
                        jsonObj.has("auth_token") -> jsonObj.getString("auth_token")
                        jsonObj.has("authToken") -> jsonObj.getString("authToken")
                        jsonObj.has("token") -> jsonObj.getString("token")
                        else -> null
                    }

                    val deviceName = when {
                        jsonObj.has("device_name") -> jsonObj.getString("device_name")
                        jsonObj.has("deviceName") -> jsonObj.getString("deviceName")
                        else -> "PC Server"
                    }

                    if (!url.isNullOrBlank() && !token.isNullOrBlank()) {
                        return PairingPayload(
                            serverUrl = normalizeUrl(url),
                            authToken = token,
                            deviceName = deviceName
                        )
                    }
                }
            } catch (e: Exception) {
                // Fallthrough to URI/URL parsing
            }

            // 2. Try parsing as brainlink:// or http(s):// URI
            try {
                if (trimmed.startsWith("brainlink://", ignoreCase = true) ||
                    trimmed.startsWith("http://", ignoreCase = true) ||
                    trimmed.startsWith("https://", ignoreCase = true)
                ) {
                    val uri = Uri.parse(trimmed)
                    val server = uri.getQueryParameter("server")
                        ?: uri.getQueryParameter("server_url")
                        ?: if (trimmed.startsWith("http", ignoreCase = true)) {
                            "${uri.scheme}://${uri.host}${if (uri.port != -1) ":${uri.port}" else ""}"
                        } else null

                    val token = uri.getQueryParameter("token")
                        ?: uri.getQueryParameter("auth_token")
                        ?: uri.fragment?.removePrefix("token=")

                    val device = uri.getQueryParameter("name")
                        ?: uri.getQueryParameter("device_name")
                        ?: "PC Server"

                    if (!server.isNullOrBlank() && !token.isNullOrBlank()) {
                        return PairingPayload(
                            serverUrl = normalizeUrl(server),
                            authToken = token,
                            deviceName = device
                        )
                    }
                }
            } catch (e: Exception) {
                // Fallthrough to delimited parsing
            }

            // 3. Try delimited format (e.g., 192.168.1.50:8000|secret_token)
            if (trimmed.contains("|")) {
                val parts = trimmed.split("|", limit = 3)
                if (parts.size >= 2) {
                    val rawServer = parts[0].trim()
                    val token = parts[1].trim()
                    val device = if (parts.size > 2) parts[2].trim() else "PC Server"
                    return PairingPayload(
                        serverUrl = normalizeUrl(rawServer),
                        authToken = token,
                        deviceName = device
                    )
                }
            }

            return null
        }

        private fun normalizeUrl(raw: String): String {
            var result = raw.trim()
            if (!result.startsWith("http://", ignoreCase = true) && !result.startsWith("https://", ignoreCase = true)) {
                result = "http://$result"
            }
            if (result.endsWith("/")) {
                result = result.substring(0, result.length - 1)
            }
            return result
        }
    }
}
