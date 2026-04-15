// ESP32 dan-mx receiver example.
//
// Listens for dan-mx frames on DANMX_UDP_PORT and drives a WS2812-style
// LED strip on DANMX_LED_PIN via FastLED. Configure pixel count and pin
// in platformio.ini build_flags.

#include <Arduino.h>
#include <FastLED.h>
#include <WiFi.h>
#include <WiFiUdp.h>

#include "danmx.h"

#ifndef DANMX_MAX_PIXELS
#define DANMX_MAX_PIXELS 300
#endif
#ifndef DANMX_LED_PIN
#define DANMX_LED_PIN 5
#endif
#ifndef DANMX_UDP_PORT
#define DANMX_UDP_PORT 6454
#endif

// Set these via a secrets.h or build_flags before flashing.
#ifndef DANMX_WIFI_SSID
#define DANMX_WIFI_SSID "your-ssid"
#endif
#ifndef DANMX_WIFI_PASS
#define DANMX_WIFI_PASS "your-password"
#endif

namespace {

constexpr size_t kMaxBytesPerPixel = 3;
uint8_t g_decode_buf[DANMX_MAX_PIXELS * kMaxBytesPerPixel];
uint8_t g_udp_buf[1500];

CRGB g_leds[DANMX_MAX_PIXELS];
danmx::StreamDecoder g_decoder;
WiFiUDP g_udp;

// Stats
uint32_t g_frames_ok = 0;
uint32_t g_frames_need_kf = 0;
uint32_t g_frames_err = 0;
uint32_t g_last_report_ms = 0;

void connect_wifi() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(DANMX_WIFI_SSID, DANMX_WIFI_PASS);
    Serial.print("wifi: connecting");
    while (WiFi.status() != WL_CONNECTED) {
        delay(250);
        Serial.print(".");
    }
    Serial.printf("\nwifi: ip=%s\n", WiFi.localIP().toString().c_str());
}

void apply_frame(const danmx::Frame& f) {
    size_t bpp = danmx::bytes_per_pixel(f.color_space);
    uint16_t n = f.pixel_count;
    if (f.start_pixel >= DANMX_MAX_PIXELS) return;
    if (uint32_t(f.start_pixel) + n > DANMX_MAX_PIXELS) {
        n = DANMX_MAX_PIXELS - f.start_pixel;
    }
    for (uint16_t i = 0; i < n; ++i) {
        uint8_t r, g, b;
        danmx::unpack_pixel(f.color_space, f.payload + i * bpp, r, g, b);
        g_leds[f.start_pixel + i] = CRGB(r, g, b);
    }
    FastLED.show();
}

const char* status_str(danmx::DecodeStatus s) {
    switch (s) {
        case danmx::DecodeStatus::OK: return "ok";
        case danmx::DecodeStatus::NEED_KEYFRAME: return "need-keyframe";
        case danmx::DecodeStatus::SHORT_PACKET: return "short";
        case danmx::DecodeStatus::BAD_MAGIC: return "bad-magic";
        case danmx::DecodeStatus::BAD_VERSION: return "bad-version";
        case danmx::DecodeStatus::BAD_ENCODING: return "bad-encoding";
        case danmx::DecodeStatus::BAD_COLOR_SPACE: return "bad-colorspace";
        case danmx::DecodeStatus::OVERFLOW_PIXELS: return "overflow";
        case danmx::DecodeStatus::TRUNCATED_BODY: return "truncated";
    }
    return "?";
}

}  // namespace

void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.println("\ndan-mx esp32 receiver");

    FastLED.addLeds<WS2812B, DANMX_LED_PIN, GRB>(g_leds, DANMX_MAX_PIXELS);
    FastLED.clear(true);

    g_decoder.init(g_decode_buf, sizeof(g_decode_buf));

    connect_wifi();
    g_udp.begin(DANMX_UDP_PORT);
    Serial.printf("udp: listening on :%d\n", DANMX_UDP_PORT);
    Serial.printf("leds: %d pixels on pin %d\n", DANMX_MAX_PIXELS, DANMX_LED_PIN);
}

void loop() {
    int packet_len = g_udp.parsePacket();
    if (packet_len > 0) {
        int n = g_udp.read(g_udp_buf, sizeof(g_udp_buf));
        if (n > 0) {
            danmx::Frame frame;
            auto st = g_decoder.decode(g_udp_buf, size_t(n), frame);
            if (st == danmx::DecodeStatus::OK) {
                apply_frame(frame);
                g_frames_ok++;
            } else if (st == danmx::DecodeStatus::NEED_KEYFRAME) {
                g_frames_need_kf++;
            } else {
                g_frames_err++;
                Serial.printf("decode: %s (len=%d)\n", status_str(st), n);
            }
        }
    }

    uint32_t now = millis();
    if (now - g_last_report_ms >= 2000) {
        g_last_report_ms = now;
        Serial.printf("frames: ok=%u need-kf=%u err=%u\n",
                      g_frames_ok, g_frames_need_kf, g_frames_err);
    }
}
