package com.antigravity.brainlink.network

import android.content.ContentResolver
import android.net.Uri
import okhttp3.MediaType
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.RequestBody
import okio.BufferedSink
import java.io.InputStream

class ProgressRequestBody(
    private val contentResolver: ContentResolver,
    private val uri: Uri,
    private val contentTypeString: String,
    private val totalLength: Long,
    private val onProgress: (bytesWritten: Long, totalBytes: Long, speedBytesPerSec: Long) -> Unit
) : RequestBody() {

    companion object {
        private const val BUFFER_SIZE = 64 * 1024 // 64KB buffer for smooth local Wi-Fi streaming
        private const val SPEED_WINDOW_MS = 1000L
    }

    override fun contentType(): MediaType? {
        return contentTypeString.toMediaTypeOrNull()
    }

    override fun contentLength(): Long {
        return if (totalLength > 0) totalLength else -1
    }

    override fun writeTo(sink: BufferedSink) {
        val inputStream: InputStream = contentResolver.openInputStream(uri)
            ?: throw IllegalStateException("Cannot open input stream for URI: $uri")

        inputStream.use { stream ->
            val buffer = ByteArray(BUFFER_SIZE)
            var bytesWritten = 0L
            var read: Int

            var lastProgressReportTime = System.currentTimeMillis()
            var bytesWrittenInWindow = 0L
            var currentSpeed = 0L

            while (stream.read(buffer).also { read = it } != -1) {
                sink.write(buffer, 0, read)
                bytesWritten += read
                bytesWrittenInWindow += read

                val now = System.currentTimeMillis()
                val elapsed = now - lastProgressReportTime

                if (elapsed >= 200L) { // Report progress every 200ms
                    currentSpeed = (bytesWrittenInWindow * 1000L) / elapsed.coerceAtLeast(1L)
                    onProgress(bytesWritten, totalLength, currentSpeed)
                    lastProgressReportTime = now
                    bytesWrittenInWindow = 0L
                }
            }

            // Final progress update
            onProgress(bytesWritten, totalLength, currentSpeed)
        }
    }
}
