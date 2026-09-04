package com.antigravity.brainlink.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.antigravity.brainlink.data.PairingPayload
import com.antigravity.brainlink.data.PreferencesManager
import com.antigravity.brainlink.ui.components.QrCameraPreview
import com.antigravity.brainlink.ui.theme.BgDark
import com.antigravity.brainlink.ui.theme.BrainLinkTheme
import com.antigravity.brainlink.ui.theme.CyanPrimary
import com.antigravity.brainlink.ui.theme.TextPrimary

class QrScannerActivity : ComponentActivity() {

    private var hasCameraPermission by mutableStateOf(false)

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted: Boolean ->
        hasCameraPermission = isGranted
        if (!isGranted) {
            Toast.makeText(this, "Camera permission is required to scan QR codes", Toast.LENGTH_LONG).show()
            finish()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        checkCameraPermission()

        setContent {
            BrainLinkTheme {
                Scaffold(
                    topBar = {
                        @OptIn(ExperimentalMaterial3Api::class)
                        TopAppBar(
                            title = { Text("Scan PC QR Code", color = TextPrimary) },
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
                        if (hasCameraPermission) {
                            QrCameraPreview(
                                onQrCodeDetected = { rawQr ->
                                    handleQrDetected(rawQr)
                                },
                                modifier = Modifier.fillMaxSize()
                            )

                            Text(
                                text = "Point camera at the QR code on your PC",
                                style = MaterialTheme.typography.bodyMedium,
                                color = TextPrimary,
                                modifier = Modifier
                                    .align(Alignment.BottomCenter)
                                    .padding(bottom = 48.dp)
                            )
                        } else {
                            Box(
                                modifier = Modifier.fillMaxSize(),
                                contentAlignment = Alignment.Center
                            ) {
                                CircularProgressIndicator(color = CyanPrimary)
                            }
                        }
                    }
                }
            }
        }
    }

    private fun checkCameraPermission() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            hasCameraPermission = true
        } else {
            requestPermissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    private fun handleQrDetected(rawQr: String) {
        val payload = PairingPayload.parse(rawQr)
        if (payload != null) {
            PreferencesManager.getInstance(this).savePairing(payload)
            runOnUiThread {
                Toast.makeText(this, "Paired with ${payload.serverUrl} successfully!", Toast.LENGTH_SHORT).show()
                setResult(RESULT_OK)
                finish()
            }
        } else {
            runOnUiThread {
                Toast.makeText(this, "Invalid BrainLink QR code. Please try again.", Toast.LENGTH_SHORT).show()
            }
        }
    }
}
