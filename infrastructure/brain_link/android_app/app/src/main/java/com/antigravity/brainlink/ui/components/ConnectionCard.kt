package com.antigravity.brainlink.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Computer
import androidx.compose.material.icons.filled.LinkOff
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.antigravity.brainlink.data.PairingPayload
import com.antigravity.brainlink.ui.theme.*

@Composable
fun ConnectionCard(
    pairing: PairingPayload?,
    onScanQrClick: () -> Unit,
    onTestPingClick: () -> Unit,
    onDisconnectClick: () -> Unit,
    pingStatus: String?,
    isPinging: Boolean,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .border(1.dp, CardBorder, RoundedCornerShape(16.dp)),
        colors = CardDefaults.cardColors(containerColor = SurfaceDark),
        shape = RoundedCornerShape(16.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(20.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(10.dp)
                            .clip(CircleShape)
                            .background(if (pairing != null) EmeraldSuccess else CoralError)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = if (pairing != null) "PAIRED & READY" else "NOT PAIRED",
                        style = MaterialTheme.typography.labelSmall,
                        color = if (pairing != null) EmeraldSuccess else CoralError,
                        fontWeight = FontWeight.Bold
                    )
                }

                if (pairing != null) {
                    IconButton(
                        onClick = onDisconnectClick,
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.LinkOff,
                            contentDescription = "Disconnect",
                            tint = TextMuted
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(14.dp))

            if (pairing != null) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.Computer,
                        contentDescription = "PC Server",
                        tint = CyanPrimary,
                        modifier = Modifier.size(28.dp)
                    )
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text(
                            text = pairing.deviceName,
                            style = MaterialTheme.typography.titleLarge,
                            color = TextPrimary
                        )
                        Text(
                            text = pairing.serverUrl,
                            style = MaterialTheme.typography.bodyMedium,
                            color = CyanPrimary
                        )
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                Text(
                    text = "Token: ${pairing.authToken.take(8)}••••••••",
                    style = MaterialTheme.typography.labelSmall,
                    color = TextMuted
                )

                AnimatedVisibility(visible = pingStatus != null) {
                    Text(
                        text = pingStatus ?: "",
                        style = MaterialTheme.typography.bodyMedium,
                        color = if (pingStatus?.contains("HTTP 200") == true || pingStatus?.contains("OK") == true) EmeraldSuccess else AmberWarning,
                        modifier = Modifier.padding(top = 8.dp)
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))

                Button(
                    onClick = onTestPingClick,
                    enabled = !isPinging,
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = SurfaceElevated),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    if (isPinging) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            color = CyanPrimary,
                            strokeWidth = 2.dp
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Pinging PC...")
                    } else {
                        Icon(Icons.Default.Refresh, contentDescription = "Ping", tint = CyanPrimary)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Test Connection", color = TextPrimary)
                    }
                }
            } else {
                Text(
                    text = "Pair with your PC by scanning the QR code displayed on the BrainLink dashboard.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextSecondary
                )

                Spacer(modifier = Modifier.height(16.dp))

                Button(
                    onClick = onScanQrClick,
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = CyanPrimary),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.QrCodeScanner,
                        contentDescription = "Scan QR",
                        tint = BgDark
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Scan PC QR Code",
                        color = BgDark,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }
}
