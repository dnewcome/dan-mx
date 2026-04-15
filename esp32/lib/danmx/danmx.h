// dan-mx receiver — pure C++ decoder, no Arduino dependencies.
//
// The decoder is stateful (it retains the previous frame's payload so
// DELTA frames can be reconstructed) but does not allocate: the caller
// owns the backing buffer and passes it in via `init`.
//
// Wire format (14-byte big-endian header):
//
//   magic        4B   "DMX2"
//   version      1B   currently 1
//   flags        1B   reserved
//   encoding     1B   0=RAW, 1=RLE, 2=DELTA
//   color_space  1B   0=RGB888, 1=RGB565, 2=G6R5B5, 3=RGB888_LINEAR
//   transfer     1B   0=LINEAR, 1=GAMMA_22, 2=SRGB
//   seq          1B
//   start_pixel  2B
//   pixel_count  2B
//   body ...

#pragma once

#include <cstddef>
#include <cstdint>

namespace danmx {

enum class EncodingMode : uint8_t {
    RAW = 0,
    RLE = 1,
    DELTA = 2,
};

enum class ColorSpace : uint8_t {
    RGB888 = 0,
    RGB565 = 1,
    G6R5B5 = 2,
    RGB888_LINEAR = 3,
};

enum class TransferFunction : uint8_t {
    LINEAR = 0,
    GAMMA_22 = 1,
    SRGB = 2,
};

enum class DecodeStatus : uint8_t {
    OK,                 // `out` holds the fully-reconstructed payload
    NEED_KEYFRAME,      // DELTA received before a usable reference — wait
    SHORT_PACKET,
    BAD_MAGIC,
    BAD_VERSION,
    BAD_ENCODING,
    BAD_COLOR_SPACE,
    OVERFLOW_PIXELS,    // pixel_count exceeds the configured buffer
    TRUNCATED_BODY,     // RLE ran out of bytes before pixel_count
};

struct Frame {
    uint8_t seq;
    uint16_t start_pixel;
    uint16_t pixel_count;
    EncodingMode encoding;
    ColorSpace color_space;
    TransferFunction transfer;
    const uint8_t* payload;   // points into the decoder's buffer; bpp * pixel_count bytes
    size_t payload_len;
};

size_t bytes_per_pixel(ColorSpace cs);

// Stateful decoder. The caller supplies a backing buffer of at least
// `buf_len` bytes — which must be large enough for the biggest expected
// frame (bytes_per_pixel(cs) * pixel_count). The decoder writes decoded
// payloads into this buffer and returns a Frame pointing into it.
class StreamDecoder {
public:
    void init(uint8_t* buf, size_t buf_len);

    // Decode one wire packet. Returns OK and fills `out` on success.
    // On NEED_KEYFRAME / any error status, `out` is not valid.
    DecodeStatus decode(const uint8_t* data, size_t len, Frame& out);

    bool has_reference() const { return have_ref_; }

private:
    uint8_t* buf_ = nullptr;
    size_t buf_len_ = 0;
    size_t ref_len_ = 0;           // bytes of `buf_` populated by the last good frame
    uint16_t ref_pixel_count_ = 0;
    ColorSpace ref_color_space_ = ColorSpace::RGB888;
    bool have_ref_ = false;
};

// RLE decoder used by StreamDecoder; exposed for unit tests.
// Writes exactly `pixel_count * bpp` bytes into `out`. Returns number of
// body bytes consumed, or SIZE_MAX on truncation.
size_t rle_decode(const uint8_t* body, size_t body_len, size_t bpp,
                  size_t pixel_count, uint8_t* out);

// Unpack one pixel from a packed color space into 8-bit R,G,B.
// Safe for call-site use when driving LED strips pixel-at-a-time.
void unpack_pixel(ColorSpace cs, const uint8_t* packed,
                  uint8_t& r, uint8_t& g, uint8_t& b);

}  // namespace danmx
