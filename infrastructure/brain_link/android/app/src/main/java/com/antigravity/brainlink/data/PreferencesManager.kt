package com.antigravity.brainlink.data

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class PreferencesManager private constructor(context: Context) {

    private val prefs: SharedPreferences = createEncryptedPreferences(context)

    private val _pairingState = MutableStateFlow(getPairingPayload())
    val pairingState: StateFlow<PairingPayload?> = _pairingState.asStateFlow()

    companion object {
        private const val TAG = "PreferencesManager"
        private const val PREFS_FILE = "secure_brainlink_prefs"
        private const val KEY_SERVER_URL = "key_server_url"
        private const val KEY_AUTH_TOKEN = "key_auth_token"
        private const val KEY_DEVICE_NAME = "key_device_name"
        private const val KEY_PAIRED_AT = "key_paired_at"

        @Volatile
        private var INSTANCE: PreferencesManager? = null

        fun getInstance(context: Context): PreferencesManager {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: PreferencesManager(context.applicationContext).also { INSTANCE = it }
            }
        }

        private fun createEncryptedPreferences(context: Context): SharedPreferences {
            return try {
                val masterKey = MasterKey.Builder(context)
                    .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                    .build()

                EncryptedSharedPreferences.create(
                    context,
                    PREFS_FILE,
                    masterKey,
                    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
                )
            } catch (e: Exception) {
                Log.e(TAG, "Failed to initialize EncryptedSharedPreferences, falling back to standard prefs", e)
                context.getSharedPreferences(PREFS_FILE, Context.MODE_PRIVATE)
            }
        }
    }

    fun savePairing(payload: PairingPayload) {
        prefs.edit()
            .putString(KEY_SERVER_URL, payload.serverUrl)
            .putString(KEY_AUTH_TOKEN, payload.authToken)
            .putString(KEY_DEVICE_NAME, payload.deviceName)
            .putLong(KEY_PAIRED_AT, payload.pairedAt)
            .apply()
        _pairingState.value = payload
    }

    fun getPairingPayload(): PairingPayload? {
        val serverUrl = prefs.getString(KEY_SERVER_URL, null) ?: return null
        val authToken = prefs.getString(KEY_AUTH_TOKEN, null) ?: return null
        val deviceName = prefs.getString(KEY_DEVICE_NAME, "PC Server") ?: "PC Server"
        val pairedAt = prefs.getLong(KEY_PAIRED_AT, 0L)

        return PairingPayload(
            serverUrl = serverUrl,
            authToken = authToken,
            deviceName = deviceName,
            pairedAt = pairedAt
        )
    }

    fun isPaired(): Boolean {
        return getPairingPayload() != null
    }

    fun clearPairing() {
        prefs.edit().clear().apply()
        _pairingState.value = null
    }
}
