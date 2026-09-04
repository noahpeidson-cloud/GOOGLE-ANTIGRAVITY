package com.antigravity.brainlink.ui

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CloudUpload
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.antigravity.brainlink.data.PreferencesManager
import com.antigravity.brainlink.data.UploadStatus
import com.antigravity.brainlink.service.FileUploadService
import com.antigravity.brainlink.ui.components.UploadProgressCard
import com.antigravity.brainlink.ui.theme.*

class ShareReceiverActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val uris = extractUrisFromIntent(intent)
        if (uris.isEmpty()) {
            Toast.makeText(this, "No video files found in share intent", Toast.LENGTH_SHORT).show()
            finish()
            return
        }

        val prefsManager = PreferencesManager.getInstance(this)
        if (prefsManager.isPaired()) {
            FileUploadService.startUpload(this, uris)
        }

        setContent {
            BrainLinkTheme {
                val pairing by prefsManager.pairingState.collectAsState()
                val uploadList by FileUploadService.uploadList.collectAsState()

                Scaffold(
                    topBar = {
                        @OptIn(ExperimentalMaterial3Api::class)
                        TopAppBar(
                            title = {
                                Text(
                                    text = "Send to BrainLink PC",
                                    color = TextPrimary,
                                    style = MaterialTheme.typography.titleLarge
                                )
                            },
                            navigationIcon = {
                                IconButton(onClick = { finish() }) {
                                    Icon(
                                        imageVector = Icons.Default.ArrowBack,
                                        contentDescription = "Back",
                                        tint = TextPrimary
                                    )
                                }
                            },
                            colors = TopAppBarDefaults.topAppBarColors(containerColor = BgDark)
                        )
                    }
                ) { innerPadding ->
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(innerPadding)
                            .background(BgDark)
                    ) {
                        if (pairing == null) {
                            UnpairedWarning(
                                onPairClick = {
                                    startActivity(Intent(this@ShareReceiverActivity, QrScannerActivity::class.java))
                                },
                                modifier = Modifier
                                    .align(Alignment.Center)
                                    .padding(24.dp)
                            )
                        } else {
                            Column(
                                modifier = Modifier
                                    .fillMaxSize()
                                    .padding(16.dp)
                            ) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        text = "Target: ${pairing?.serverUrl}",
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = CyanPrimary,
                                        fontWeight = FontWeight.SemiBold
                                    )

                                    val allCompleted = uploadList.isNotEmpty() && uploadList.all {
                                        it.status == UploadStatus.COMPLETED || it.status == UploadStatus.FAILED
                                    }

                                    Button(
                                        onClick = { finish() },
                                        colors = ButtonDefaults.buttonColors(
                                            containerColor = if (allCompleted) EmeraldSuccess else SurfaceElevated
                                        ),
                                        shape = RoundedCornerShape(8.dp)
                                    ) {
                                        Text(if (allCompleted) "Done" else "Background")
                                    }
                                }

                                Spacer(modifier = Modifier.height(16.dp))

                                LazyColumn(
                                    verticalArrangement = Arrangement.spacedBy(12.dp),
                                    modifier = Modifier.fillMaxSize()
                                ) {
                                    items(uploadList, key = { it.id }) { item ->
                                        UploadProgressCard(item = item)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    private fun extractUrisFromIntent(intent: Intent?): List<Uri> {
        if (intent == null) return emptyList()

        val action = intent.action
        val type = intent.type ?: ""

        if (!type.startsWith("video/") && type != "*/*") {
            // Allow video sharing
        }

        val result = mutableListOf<Uri>()

        if (Intent.ACTION_SEND == action) {
            val uri = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
            } else {
                @Suppress("DEPRECATION")
                intent.getParcelableExtra(Intent.EXTRA_STREAM)
            }
            if (uri != null) result.add(uri)
        } else if (Intent.ACTION_SEND_MULTIPLE == action) {
            val uris = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM, Uri::class.java)
            } else {
                @Suppress("DEPRECATION")
                intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM)
            }
            if (!uris.isNullOrEmpty()) {
                result.addAll(uris)
            }
        }

        return result
    }

    @Composable
    private fun UnpairedWarning(
        onPairClick: () -> Unit,
        modifier: Modifier = Modifier
    ) {
        Card(
            modifier = modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = SurfaceDark),
            shape = RoundedCornerShape(16.dp)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Icon(
                    imageVector = Icons.Default.CloudUpload,
                    contentDescription = null,
                    tint = CoralError,
                    modifier = Modifier.size(48.dp)
                )

                Spacer(modifier = Modifier.height(16.dp))

                Text(
                    text = "PC Not Paired",
                    style = MaterialTheme.typography.titleLarge,
                    color = TextPrimary
                )

                Spacer(modifier = Modifier.height(8.dp))

                Text(
                    text = "Before you can share videos, scan the QR code on your PC dashboard to pair.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextSecondary,
                    modifier = Modifier.padding(horizontal = 8.dp)
                )

                Spacer(modifier = Modifier.height(20.dp))

                Button(
                    onClick = onPairClick,
                    colors = ButtonDefaults.buttonColors(containerColor = CyanPrimary),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Icon(Icons.Default.QrCodeScanner, contentDescription = null, tint = BgDark)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Pair with PC Now", color = BgDark, fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}
