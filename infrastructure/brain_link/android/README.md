# BrainLink Android App

Native Kotlin Android client for high-performance, local Wi-Fi 4K video transfer from Android Gallery to PC.

## Features

1. **CameraX & ML Kit QR Code Pairing:**
   - Real-time QR barcode scanner with animated viewfinder.
   - Automatically decodes server IP, port, and authentication token.
   - Saves credentials securely using `androidx.security.crypto.EncryptedSharedPreferences` backed by Android Keystore (AES-256-GCM / AES-256-SIV).

2. **Native Android Share Integration (`ACTION_SEND` & `ACTION_SEND_MULTIPLE`):**
   - Registered `video/*` intent filters in `AndroidManifest.xml`.
   - Allows users to select 1 or multiple 4K/HDR videos directly in Samsung Gallery / Google Photos / Files and tap **Share -> Send to BrainLink PC**.

3. **Streamed / Chunked 1GB+ 4K Video Uploads:**
   - Implements custom `ProgressRequestBody` on top of OkHttp.
   - Pipes `InputStream` directly to network `BufferedSink` in 64KB buffers without buffering the video into RAM (zero OOM risk on multi-gigabyte 4K clips).
   - Real-time MB/s throughput and progress monitoring.
   - Runs in a `ForegroundService` with persistent progress notification and `WakeLock` / `WifiLock` to prevent Android OS Doze or Wi-Fi throttling from terminating long transfers.

## Architecture

```
com.antigravity.brainlink/
├── BrainLinkApp.kt              # App init & notification channels
├── data/
│   ├── PairingPayload.kt        # Multi-format QR Parser (JSON, URI, Delimited)
│   ├── PreferencesManager.kt    # EncryptedSharedPreferences wrapper
│   ├── UploadItem.kt            # Reactive upload state model
│   └── VideoMetadataHelper.kt   # ContentResolver metadata extractor
├── network/
│   ├── BrainLinkApiClient.kt    # OkHttp client & multipart upload
│   └── ProgressRequestBody.kt   # Zero-copy streaming RequestBody
├── service/
│   └── FileUploadService.kt     # Foreground Service with WakeLock/WifiLock
└── ui/
    ├── MainActivity.kt          # Dashboard & test upload trigger
    ├── QrScannerActivity.kt     # CameraX + ML Kit scanner activity
    ├── ShareReceiverActivity.kt # ACTION_SEND / ACTION_SEND_MULTIPLE entrypoint
    ├── components/              # Jetpack Compose UI components
    └── theme/                   # Material 3 Dark theme
```

## QR Code Schema

The QR scanner supports any of the following formats:

### JSON:
```json
{
  "server_url": "http://192.168.1.50:8000",
  "auth_token": "your_secure_auth_token_here",
  "device_name": "Noah-PC"
}
```

### URI:
```
brainlink://pair?server=http://192.168.1.50:8000&token=your_secure_auth_token_here&name=Noah-PC
```

### Pipe Delimited:
```
192.168.1.50:8000|your_secure_auth_token_here|Noah-PC
```
