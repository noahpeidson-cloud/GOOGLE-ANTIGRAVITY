package com.antigravity.brainlink.data

import android.net.Uri

enum class UploadStatus {
    IDLE,
    QUEUED,
    UPLOADING,
    COMPLETED,
    FAILED,
    CANCELLED
}

data class UploadItem(
    val id: String,
    val uri: Uri,
    val fileName: String,
    val fileSize: Long,
    val bytesTransferred: Long = 0L,
    val progress: Float = 0f,
    val transferSpeedBytesPerSec: Long = 0L,
    val status: UploadStatus = UploadStatus.QUEUED,
    val errorMessage: String? = null,
    val startedAt: Long = System.currentTimeMillis()
) {
    val progressPercent: Int
        get() = (progress * 100).toInt().coerceIn(0, 100)

    val formattedSpeed: String
        get() {
            val mbps = transferSpeedBytesPerSec / (1024.0 * 1024.0)
            return String.format("%.1f MB/s", mbps)
        }

    val formattedProgressSize: String
        get() {
            val transferredMb = bytesTransferred / (1024.0 * 1024.0)
            val totalMb = fileSize / (1024.0 * 1024.0)
            return String.format("%.1f / %.1f MB", transferredMb, totalMb)
        }
}
