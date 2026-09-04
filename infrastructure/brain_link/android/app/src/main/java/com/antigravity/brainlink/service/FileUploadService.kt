package com.antigravity.brainlink.service

import android.app.Notification
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import com.antigravity.brainlink.BrainLinkApp
import com.antigravity.brainlink.R
import com.antigravity.brainlink.data.UploadItem
import com.antigravity.brainlink.data.UploadStatus
import com.antigravity.brainlink.data.VideoMetadataHelper
import com.antigravity.brainlink.network.BrainLinkApiClient
import com.antigravity.brainlink.ui.MainActivity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.UUID

class FileUploadService : Service() {

    companion object {
        private const val TAG = "FileUploadService"
        private const val NOTIFICATION_ID = 1001

        const val ACTION_START_UPLOAD = "com.antigravity.brainlink.action.START_UPLOAD"
        const val ACTION_CANCEL_UPLOAD = "com.antigravity.brainlink.action.CANCEL_UPLOAD"
        const val EXTRA_VIDEO_URIS = "com.antigravity.brainlink.extra.VIDEO_URIS"

        private val _uploadList = MutableStateFlow<List<UploadItem>>(emptyList())
        val uploadList: StateFlow<List<UploadItem>> = _uploadList.asStateFlow()

        fun startUpload(context: Context, uris: List<Uri>) {
            val intent = Intent(context, FileUploadService::class.java).apply {
                action = ACTION_START_UPLOAD
                putParcelableArrayListExtra(EXTRA_VIDEO_URIS, ArrayList(uris))
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }
    }

    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private lateinit var apiClient: BrainLinkApiClient
    private lateinit var notificationManager: NotificationManager
    private var wakeLock: PowerManager.WakeLock? = null
    private var wifiLock: WifiManager.WifiLock? = null

    override fun onCreate() {
        super.onCreate()
        apiClient = BrainLinkApiClient(this)
        notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        acquireLocks()
    }

    private fun acquireLocks() {
        try {
            val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
            wakeLock = powerManager.newWakeLock(
                PowerManager.PARTIAL_WAKE_LOCK,
                "BrainLink:UploadWakeLock"
            ).apply {
                acquire(30 * 60 * 1000L) // Max 30 min safety timeout
            }

            val wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            wifiLock = wifiManager.createWifiLock(
                WifiManager.WIFI_MODE_FULL_HIGH_PERF,
                "BrainLink:UploadWifiLock"
            ).apply {
                acquire()
            }
        } catch (e: Exception) {
            Log.w(TAG, "Could not acquire full wakelock/wifilock", e)
        }
    }

    private fun releaseLocks() {
        try {
            if (wakeLock?.isHeld == true) wakeLock?.release()
            if (wifiLock?.isHeld == true) wifiLock?.release()
        } catch (e: Exception) {
            Log.w(TAG, "Error releasing locks", e)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_CANCEL_UPLOAD -> {
                stopSelf()
                return START_NOT_STICKY
            }
            ACTION_START_UPLOAD -> {
                val uris = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    intent.getParcelableArrayListExtra(EXTRA_VIDEO_URIS, Uri::class.java)
                } else {
                    @Suppress("DEPRECATION")
                    intent.getParcelableArrayListExtra(EXTRA_VIDEO_URIS)
                }

                if (!uris.isNullOrEmpty()) {
                    startForeground(NOTIFICATION_ID, buildInitialNotification(uris.size))
                    enqueueAndProcessUploads(uris)
                } else {
                    stopSelf()
                }
            }
            else -> stopSelf()
        }
        return START_NOT_STICKY
    }

    private fun enqueueAndProcessUploads(uris: List<Uri>) {
        serviceScope.launch {
            val newItems = uris.map { uri ->
                val info = VideoMetadataHelper.extractVideoInfo(this@FileUploadService, uri)
                UploadItem(
                    id = UUID.randomUUID().toString(),
                    uri = uri,
                    fileName = info.fileName,
                    fileSize = info.fileSize,
                    status = UploadStatus.QUEUED
                )
            }

            _uploadList.value = _uploadList.value + newItems

            for (item in newItems) {
                uploadSingleItem(item)
            }

            // All uploads finished
            updateNotificationComplete()
            stopForeground(STOP_FOREGROUND_DETACH)
            stopSelf()
        }
    }

    private suspend fun uploadSingleItem(item: UploadItem) {
        updateItemStatus(item.id, UploadStatus.UPLOADING)

        val result = apiClient.uploadVideo(
            videoUri = item.uri,
            onProgress = { bytesWritten, totalBytes, speedBytesPerSec ->
                val progress = if (totalBytes > 0) bytesWritten.toFloat() / totalBytes else 0f
                updateItemProgress(item.id, bytesWritten, totalBytes, progress, speedBytesPerSec)
                updateNotificationProgress(item.fileName, (progress * 100).toInt(), speedBytesPerSec)
            }
        )

        if (result.isSuccess) {
            updateItemStatus(item.id, UploadStatus.COMPLETED)
        } else {
            val error = result.exceptionOrNull()?.localizedMessage ?: "Upload failed"
            updateItemStatus(item.id, UploadStatus.FAILED, error)
        }
    }

    private fun updateItemProgress(
        id: String,
        bytesWritten: Long,
        totalBytes: Long,
        progress: Float,
        speedBytesPerSec: Long
    ) {
        _uploadList.value = _uploadList.value.map {
            if (it.id == id) {
                it.copy(
                    bytesTransferred = bytesWritten,
                    fileSize = if (totalBytes > 0) totalBytes else it.fileSize,
                    progress = progress,
                    transferSpeedBytesPerSec = speedBytesPerSec
                )
            } else it
        }
    }

    private fun updateItemStatus(id: String, status: UploadStatus, error: String? = null) {
        _uploadList.value = _uploadList.value.map {
            if (it.id == id) {
                it.copy(status = status, errorMessage = error)
            } else it
        }
    }

    private fun buildInitialNotification(totalCount: Int): Notification {
        val contentIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, BrainLinkApp.UPLOAD_NOTIFICATION_CHANNEL_ID)
            .setContentTitle("BrainLink: Uploading $totalCount video(s)")
            .setContentText("Preparing high-speed stream to PC...")
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setContentIntent(contentIntent)
            .setProgress(100, 0, true)
            .setOngoing(true)
            .build()
    }

    private fun updateNotificationProgress(fileName: String, percent: Int, speedBytesPerSec: Long) {
        val speedMb = speedBytesPerSec / (1024.0 * 1024.0)
        val speedText = String.format("%.1f MB/s", speedMb)

        val notification = NotificationCompat.Builder(this, BrainLinkApp.UPLOAD_NOTIFICATION_CHANNEL_ID)
            .setContentTitle("Uploading $fileName")
            .setContentText("$percent% • $speedText")
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setProgress(100, percent, false)
            .setOngoing(true)
            .build()

        notificationManager.notify(NOTIFICATION_ID, notification)
    }

    private fun updateNotificationComplete() {
        val notification = NotificationCompat.Builder(this, BrainLinkApp.UPLOAD_NOTIFICATION_CHANNEL_ID)
            .setContentTitle("Uploads Completed")
            .setContentText("Videos transferred successfully to BrainLink PC")
            .setSmallIcon(android.R.drawable.stat_sys_upload_done)
            .setAutoCancel(true)
            .build()

        notificationManager.notify(NOTIFICATION_ID, notification)
    }

    override fun onDestroy() {
        super.onDestroy()
        releaseLocks()
        serviceScope.cancel()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
