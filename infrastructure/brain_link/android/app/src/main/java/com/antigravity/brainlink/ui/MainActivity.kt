package com.antigravity.brainlink.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.VideoLibrary
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.antigravity.brainlink.data.PairingPayload
import com.antigravity.brainlink.data.PreferencesManager
import com.antigravity.brainlink.network.BrainLinkApiClient
import com.antigravity.brainlink.service.FileUploadService
import com.antigravity.brainlink.ui.components.ConnectionCard
import com.antigravity.brainlink.ui.components.UploadProgressCard
import com.antigravity.brainlink.ui.theme.*
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private lateinit var prefsManager: PreferencesManager
    private lateinit var apiClient: BrainLinkApiClient

    private val selectVideoLauncher = registerForActivityResult(
        ActivityResultContracts.GetMultipleContents()
    ) { uris: List<Uri> ->
        if (uris.isNotEmpty()) {
            if (prefsManager.isPaired()) {
                FileUploadService.startUpload(this, uris)
            } else {
                Toast.makeText(this, "Please pair with your PC first", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private val qrScannerLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == RESULT_OK) {
            Toast.makeText(this, "PC Paired successfully!", Toast.LENGTH_SHORT).show()
        }
    }

    private val requestNotificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* Permission result */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefsManager = PreferencesManager.getInstance(this)
        apiClient = BrainLinkApiClient(this)

        checkNotificationPermission()

        setContent {
            BrainLinkTheme {
                val coroutineScope = rememberCoroutineScope()
                val pairing by prefsManager.pairingState.collectAsState()
                val uploadList by FileUploadService.uploadList.collectAsState()

                var pingStatus by remember { mutableStateOf<String?>(null) }
                var isPinging by remember { mutableStateOf(false) }
                var showManualDialog by remember { mutableStateOf(false) }

                Scaffold(
                    topBar = {
                        @OptIn(ExperimentalMaterial3Api::class)
                        TopAppBar(
                            title = {
                                Text(
                                    text = "BrainLink",
                                    style = MaterialTheme.typography.headlineMedium,
                                    color = CyanPrimary,
                                    fontWeight = FontWeight.Bold
                                )
                            },
                            actions = {
                                IconButton(onClick = { showManualDialog = true }) {
                                    Icon(
                                        imageVector = Icons.Default.Edit,
                                        contentDescription = "Manual Config",
                                        tint = TextSecondary
                                    )
                                }
                            },
                            colors = TopAppBarDefaults.topAppBarColors(containerColor = BgDark)
                        )
                    },
                    floatingActionButton = {
                        if (pairing != null) {
                            FloatingActionButton(
                                onClick = { selectVideoLauncher.launch("video/*") },
                                containerColor = CyanPrimary,
                                contentColor = BgDark
                            ) {
                                Row(
                                    modifier = Modifier.padding(horizontal = 16.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(Icons.Default.VideoLibrary, contentDescription = "Pick Video")
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text("Send Video", fontWeight = FontWeight.Bold)
                                }
                            }
                        }
                    }
                ) { innerPadding ->
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(innerPadding)
                            .background(BgDark)
                    ) {
                        LazyColumn(
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(16.dp),
                            verticalArrangement = Arrangement.spacedBy(16.dp)
                        ) {
                            item {
                                ConnectionCard(
                                    pairing = pairing,
                                    onScanQrClick = {
                                        qrScannerLauncher.launch(Intent(this@MainActivity, QrScannerActivity::class.java))
                                    },
                                    onTestPingClick = {
                                        val p = pairing ?: return@ConnectionCard
                                        isPinging = true
                                        pingStatus = null
                                        coroutineScope.launch {
                                            val res = apiClient.testConnection(p.serverUrl, p.authToken)
                                            isPinging = false
                                            pingStatus = if (res.isSuccess) {
                                                "Connection verified (HTTP 200 OK)"
                                            } else {
                                                "Connection failed: ${res.exceptionOrNull()?.message}"
                                            }
                                        }
                                    },
                                    onDisconnectClick = {
                                        prefsManager.clearPairing()
                                        pingStatus = null
                                    },
                                    pingStatus = pingStatus,
                                    isPinging = isPinging
                                )
                            }

                            if (uploadList.isNotEmpty()) {
                                item {
                                    Text(
                                        text = "TRANSFERS",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = TextMuted,
                                        fontWeight = FontWeight.Bold
                                    )
                                }

                                items(uploadList, key = { it.id }) { item ->
                                    UploadProgressCard(item = item)
                                }
                            } else if (pairing != null) {
                                item {
                                    Box(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(top = 40.dp),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                            Text(
                                                text = "Ready to receive shared videos",
                                                style = MaterialTheme.typography.bodyLarge,
                                                color = TextSecondary
                                            )
                                            Spacer(modifier = Modifier.height(4.dp))
                                            Text(
                                                text = "Share 4K videos directly from your Gallery, or tap 'Send Video'",
                                                style = MaterialTheme.typography.bodyMedium,
                                                color = TextMuted
                                            )
                                        }
                                    }
                                }
                            }
                        }

                        if (showManualDialog) {
                            ManualConfigDialog(
                                initialUrl = pairing?.serverUrl ?: "http://192.168.1.100:8000",
                                initialToken = pairing?.authToken ?: "",
                                onDismiss = { showManualDialog = false },
                                onSave = { url, token ->
                                    prefsManager.savePairing(
                                        PairingPayload(
                                            serverUrl = url,
                                            authToken = token,
                                            deviceName = "Manual PC"
                                        )
                                    )
                                    showManualDialog = false
                                }
                            )
                        }
                    }
                }
            }
        }
    }

    private fun checkNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestNotificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
    }

    @Composable
    private fun ManualConfigDialog(
        initialUrl: String,
        initialToken: String,
        onDismiss: () -> Unit,
        onSave: (String, String) -> Unit
    ) {
        var serverUrl by remember { mutableStateOf(initialUrl) }
        var authToken by remember { mutableStateOf(initialToken) }

        AlertDialog(
            onDismissRequest = onDismiss,
            title = { Text("Manual PC Configuration", color = TextPrimary) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    OutlinedTextField(
                        value = serverUrl,
                        onValueChange = { serverUrl = it },
                        label = { Text("Server URL (e.g. http://192.168.1.50:8000)") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                    OutlinedTextField(
                        value = authToken,
                        onValueChange = { authToken = it },
                        label = { Text("Auth Token") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        if (serverUrl.isNotBlank() && authToken.isNotBlank()) {
                            onSave(serverUrl.trim(), authToken.trim())
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = CyanPrimary)
                ) {
                    Text("Save", color = BgDark, fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(onClick = onDismiss) {
                    Text("Cancel", color = TextSecondary)
                }
            },
            containerColor = SurfaceDark
        )
    }
}
