package com.antigravity.brainlink.network

import android.content.Context
import android.net.Uri
import android.util.Log
import com.antigravity.brainlink.data.PreferencesManager
import com.antigravity.brainlink.data.VideoMetadataHelper
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import java.io.IOException
import java.net.URLEncoder
import java.util.concurrent.TimeUnit

class BrainLinkApiClient(private val context: Context) {

    companion object {
        private const val TAG = "BrainLinkApiClient"
        private const val CONNECT_TIMEOUT_SECONDS = 15L
        private const val READ_TIMEOUT_MINUTES = 30L
        private const val WRITE_TIMEOUT_MINUTES = 30L
    }

    private val okHttpClient: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(CONNECT_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .readTimeout(READ_TIMEOUT_MINUTES, TimeUnit.MINUTES)
        .writeTimeout(WRITE_TIMEOUT_MINUTES, TimeUnit.MINUTES)
        .retryOnConnectionFailure(true)
        .build()

    private val prefsManager = PreferencesManager.getInstance(context)

    suspend fun testConnection(serverUrl: String, authToken: String): Result<String> = withContext(Dispatchers.IO) {
        try {
            val url = "$serverUrl/api/ping"
            val request = Request.Builder()
                .url(url)
                .addHeader("Authorization", "Bearer $authToken")
                .addHeader("X-Auth-Token", authToken)
                .get()
                .build()

            val response: Response = okHttpClient.newCall(request).execute()
            if (response.isSuccessful) {
                val body = response.body?.string() ?: "OK"
                Result.success(body)
            } else {
                Result.failure(IOException("Server responded with HTTP ${response.code}: ${response.message}"))
            }
        } catch (e: Exception) {
            Log.e(TAG, "testConnection failed", e)
            Result.failure(e)
        }
    }

    suspend fun uploadVideo(
        videoUri: Uri,
        onProgress: (bytesWritten: Long, totalBytes: Long, speedBytesPerSec: Long) -> Unit
    ): Result<String> = withContext(Dispatchers.IO) {
        val pairing = prefsManager.getPairingPayload()
            ?: return@withContext Result.failure(IllegalStateException("Device is not paired with a PC."))

        val videoInfo = VideoMetadataHelper.extractVideoInfo(context, videoUri)
        val uploadUrl = "${pairing.serverUrl}/api/upload"

        val progressBody = ProgressRequestBody(
            contentResolver = context.contentResolver,
            uri = videoUri,
            contentTypeString = videoInfo.mimeType,
            totalLength = videoInfo.fileSize,
            onProgress = onProgress
        )

        // Encode filename safely for HTTP Header
        val safeFileName = URLEncoder.encode(videoInfo.fileName, "UTF-8")

        // Build Multipart Form or direct streaming request
        val multipartBody = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart(
                name = "file",
                filename = videoInfo.fileName,
                body = progressBody
            )
            .build()

        val request = Request.Builder()
            .url(uploadUrl)
            .addHeader("Authorization", "Bearer ${pairing.authToken}")
            .addHeader("X-Auth-Token", pairing.authToken)
            .addHeader("X-File-Name", safeFileName)
            .addHeader("X-File-Size", videoInfo.fileSize.toString())
            .post(multipartBody)
            .build()

        try {
            Log.d(TAG, "Starting high-speed upload of ${videoInfo.fileName} (${videoInfo.fileSize} bytes) to $uploadUrl")
            val response: Response = okHttpClient.newCall(request).execute()

            if (response.isSuccessful) {
                val respBody = response.body?.string() ?: "Upload successful"
                Log.d(TAG, "Upload completed successfully: $respBody")
                Result.success(respBody)
            } else {
                val errorMsg = "Upload failed with HTTP ${response.code}: ${response.message}"
                Log.e(TAG, errorMsg)
                Result.failure(IOException(errorMsg))
            }
        } catch (e: Exception) {
            Log.e(TAG, "Upload exception for URI: $videoUri", e)
            Result.failure(e)
        }
    }
}
