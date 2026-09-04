package com.antigravity.brainlink.data

import android.content.ContentResolver
import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import java.io.File

object VideoMetadataHelper {

    data class VideoInfo(
        val fileName: String,
        val fileSize: Long,
        val mimeType: String
    )

    fun extractVideoInfo(context: Context, uri: Uri): VideoInfo {
        val resolver: ContentResolver = context.contentResolver
        var fileName = "video_${System.currentTimeMillis()}.mp4"
        var fileSize = 0L
        var mimeType = resolver.getType(uri) ?: "video/mp4"

        try {
            if (uri.scheme == ContentResolver.SCHEME_CONTENT) {
                resolver.query(uri, null, null, null, null)?.use { cursor ->
                    val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    val sizeIndex = cursor.getColumnIndex(OpenableColumns.SIZE)

                    if (cursor.moveToFirst()) {
                        if (nameIndex != -1) {
                            val name = cursor.getString(nameIndex)
                            if (!name.isNullOrBlank()) {
                                fileName = name
                            }
                        }
                        if (sizeIndex != -1 && !cursor.isNull(sizeIndex)) {
                            fileSize = cursor.getLong(sizeIndex)
                        }
                    }
                }
            } else if (uri.scheme == "file") {
                val path = uri.path
                if (path != null) {
                    val file = File(path)
                    fileName = file.name
                    fileSize = file.length()
                }
            }

            // Fallback for file size if query returned 0
            if (fileSize <= 0L) {
                try {
                    resolver.openAssetFileDescriptor(uri, "r")?.use { afd ->
                        val length = afd.length
                        if (length > 0) {
                            fileSize = length
                        }
                    }
                } catch (ignored: Exception) {
                }
            }
        } catch (e: Exception) {
            // Safe fallback
        }

        // Guarantee video extension
        if (!fileName.contains(".")) {
            fileName += ".mp4"
        }

        return VideoInfo(
            fileName = fileName,
            fileSize = fileSize,
            mimeType = mimeType
        )
    }
}
