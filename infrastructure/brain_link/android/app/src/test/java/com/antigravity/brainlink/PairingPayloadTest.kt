package com.antigravity.brainlink

import com.antigravity.brainlink.data.PairingPayload
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class PairingPayloadTest {

    @Test
    fun testParseJsonPayloadWithServerUrl() {
        val json = """{"server_url": "http://192.168.1.100:8000", "auth_token": "secret_token_123", "device_name": "Noah-PC"}"""
        val payload = PairingPayload.parse(json)

        assertNotNull(payload)
        assertEquals("http://192.168.1.100:8000", payload?.serverUrl)
        assertEquals("secret_token_123", payload?.authToken)
        assertEquals("Noah-PC", payload?.deviceName)
    }

    @Test
    fun testParseJsonPayloadWithIpAndPort() {
        val json = """{"ip": "192.168.1.55", "port": 9000, "token": "abc_xyz_789"}"""
        val payload = PairingPayload.parse(json)

        assertNotNull(payload)
        assertEquals("http://192.168.1.55:9000", payload?.serverUrl)
        assertEquals("abc_xyz_789", payload?.authToken)
    }

    @Test
    fun testParseUriScheme() {
        val uri = "brainlink://pair?server=http://192.168.1.42:8000&token=tok_456&name=StudioRig"
        val payload = PairingPayload.parse(uri)

        assertNotNull(payload)
        assertEquals("http://192.168.1.42:8000", payload?.serverUrl)
        assertEquals("tok_456", payload?.authToken)
        assertEquals("StudioRig", payload?.deviceName)
    }

    @Test
    fun testParseDelimitedString() {
        val raw = "192.168.1.99:8000|my_secure_auth_token|Workstation"
        val payload = PairingPayload.parse(raw)

        assertNotNull(payload)
        assertEquals("http://192.168.1.99:8000", payload?.serverUrl)
        assertEquals("my_secure_auth_token", payload?.authToken)
        assertEquals("Workstation", payload?.deviceName)
    }

    @Test
    fun testParseInvalidStringReturnsNull() {
        val invalid = "random invalid garbage string"
        val payload = PairingPayload.parse(invalid)
        assertNull(payload)
    }
}
