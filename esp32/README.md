# dan-mx ESP32 receiver

Reference implementation of a dan-mx receiver for ESP32, driving a
WS2812 LED strip via FastLED.

## Layout

- `lib/danmx/` — pure-C++17 decoder with no Arduino dependencies. Can be
  dropped into an ESP-IDF project, pulled into native unit tests, or
  ported to any microcontroller with a UDP stack.
- `src/main.cpp` — Arduino-framework glue: WiFi, UDP listener, FastLED
  output, basic stats over serial.
- `test/test_decoder/` — host-side Unity tests validating the wire
  decoder against byte sequences matching the Python reference.

## Build & flash

Uses [PlatformIO](https://platformio.org/).

```
cd esp32
pio run -e esp32dev                # compile
pio run -e esp32dev -t upload      # flash
pio device monitor                 # serial output
```

Override pixel count, LED pin, UDP port, and WiFi credentials via build
flags in `platformio.ini` — or pass them on the CLI:

```
pio run -e esp32dev \
    --build-flag '-DDANMX_MAX_PIXELS=144' \
    --build-flag '-DDANMX_LED_PIN=16' \
    --build-flag '-DDANMX_WIFI_SSID=\"mynet\"' \
    --build-flag '-DDANMX_WIFI_PASS=\"secret\"'
```

## Run the host-side tests

```
pio test -e native-test
```

No ESP32 required; runs on your machine. Validates RAW / RLE / DELTA
decoding, the run-of-256 boundary, NEED_KEYFRAME handling, overflow
guards, and G6R5B5 unpacking.

## Memory

The decoder holds one full payload as the delta reference. At
`DANMX_MAX_PIXELS=300` in RGB888 that's 900 bytes; in G6R5B5 it halves
to 600 bytes. Plus the 1500-byte UDP buffer. All statically allocated.

## Design notes

- Decoder is stateful but does not allocate — the caller provides the
  backing buffer via `StreamDecoder::init`.
- DELTA frames are applied in-place by XORing the RLE-decoded delta
  stream against the current reference buffer. No extra copy.
- `NEED_KEYFRAME` is the only non-error status a caller should expect
  to see regularly — it means a delta arrived before a keyframe and the
  receiver is waiting to resync.
