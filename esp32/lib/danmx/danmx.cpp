#include "danmx.h"

#include <cstring>

namespace danmx {

namespace {

constexpr uint8_t kMagic[4] = {'D', 'M', 'X', '2'};
constexpr uint8_t kVersion = 1;
constexpr size_t kHeaderLen = 14;

uint16_t read_u16_be(const uint8_t* p) {
    return (uint16_t(p[0]) << 8) | uint16_t(p[1]);
}

}  // namespace

size_t bytes_per_pixel(ColorSpace cs) {
    switch (cs) {
        case ColorSpace::RGB888:
        case ColorSpace::RGB888_LINEAR:
            return 3;
        case ColorSpace::RGB565:
        case ColorSpace::G6R5B5:
            return 2;
    }
    return 0;
}

size_t rle_decode(const uint8_t* body, size_t body_len, size_t bpp,
                  size_t pixel_count, uint8_t* out) {
    size_t i = 0;
    size_t written = 0;
    size_t decoded = 0;
    while (decoded < pixel_count) {
        if (i >= body_len) return SIZE_MAX;
        uint16_t run = body[i] == 0 ? 256 : body[i];
        i += 1;
        if (i + bpp > body_len) return SIZE_MAX;
        if (decoded + run > pixel_count) return SIZE_MAX;  // sender bug: overshoots
        for (uint16_t r = 0; r < run; ++r) {
            std::memcpy(out + written, body + i, bpp);
            written += bpp;
        }
        i += bpp;
        decoded += run;
    }
    return i;
}

void unpack_pixel(ColorSpace cs, const uint8_t* p,
                  uint8_t& r, uint8_t& g, uint8_t& b) {
    switch (cs) {
        case ColorSpace::RGB888:
        case ColorSpace::RGB888_LINEAR:
            r = p[0]; g = p[1]; b = p[2];
            return;
        case ColorSpace::RGB565: {
            uint16_t v = (uint16_t(p[0]) << 8) | uint16_t(p[1]);
            uint8_t r5 = (v >> 8) & 0xF8;
            uint8_t g6 = (v >> 3) & 0xFC;
            uint8_t b5 = (v << 3) & 0xF8;
            r = r5 | (r5 >> 5);
            g = g6 | (g6 >> 6);
            b = b5 | (b5 >> 5);
            return;
        }
        case ColorSpace::G6R5B5: {
            uint16_t v = (uint16_t(p[0]) << 8) | uint16_t(p[1]);
            uint8_t g6 = (v >> 8) & 0xFC;
            uint8_t r5 = (v >> 2) & 0xF8;
            uint8_t b5 = (v << 3) & 0xF8;
            r = r5 | (r5 >> 5);
            g = g6 | (g6 >> 6);
            b = b5 | (b5 >> 5);
            return;
        }
    }
    r = g = b = 0;
}

void StreamDecoder::init(uint8_t* buf, size_t buf_len) {
    buf_ = buf;
    buf_len_ = buf_len;
    ref_len_ = 0;
    have_ref_ = false;
}

DecodeStatus StreamDecoder::decode(const uint8_t* data, size_t len, Frame& out) {
    if (len < kHeaderLen) return DecodeStatus::SHORT_PACKET;
    if (std::memcmp(data, kMagic, 4) != 0) return DecodeStatus::BAD_MAGIC;
    if (data[4] != kVersion) return DecodeStatus::BAD_VERSION;

    EncodingMode enc = static_cast<EncodingMode>(data[6]);
    ColorSpace cs = static_cast<ColorSpace>(data[7]);
    TransferFunction tf = static_cast<TransferFunction>(data[8]);
    uint8_t seq = data[9];
    uint16_t start_pixel = read_u16_be(data + 10);
    uint16_t pixel_count = read_u16_be(data + 12);

    if (enc != EncodingMode::RAW && enc != EncodingMode::RLE && enc != EncodingMode::DELTA)
        return DecodeStatus::BAD_ENCODING;

    size_t bpp = bytes_per_pixel(cs);
    if (bpp == 0) return DecodeStatus::BAD_COLOR_SPACE;

    size_t need = size_t(pixel_count) * bpp;
    if (need > buf_len_) return DecodeStatus::OVERFLOW_PIXELS;

    const uint8_t* body = data + kHeaderLen;
    size_t body_len = len - kHeaderLen;

    if (enc == EncodingMode::RAW) {
        if (body_len < need) return DecodeStatus::TRUNCATED_BODY;
        std::memcpy(buf_, body, need);
    } else if (enc == EncodingMode::RLE) {
        if (rle_decode(body, body_len, bpp, pixel_count, buf_) == SIZE_MAX)
            return DecodeStatus::TRUNCATED_BODY;
    } else {
        // DELTA: RLE stream is the XOR against the previous full payload.
        if (!have_ref_ || ref_len_ != need ||
            ref_pixel_count_ != pixel_count || ref_color_space_ != cs) {
            return DecodeStatus::NEED_KEYFRAME;
        }
        // Decode the XOR stream into a scratch region at the tail of the buffer.
        // If the buffer is exactly sized we'd clobber the reference; require
        // headroom of one payload. For simplicity we decode byte-by-byte in place.
        size_t i = 0;
        size_t written = 0;
        size_t decoded_px = 0;
        while (decoded_px < pixel_count) {
            if (i >= body_len) return DecodeStatus::TRUNCATED_BODY;
            uint16_t run = body[i] == 0 ? 256 : body[i];
            i += 1;
            if (i + bpp > body_len) return DecodeStatus::TRUNCATED_BODY;
            if (decoded_px + run > pixel_count) return DecodeStatus::TRUNCATED_BODY;
            for (uint16_t r = 0; r < run; ++r) {
                for (size_t k = 0; k < bpp; ++k) {
                    buf_[written + k] ^= body[i + k];
                }
                written += bpp;
            }
            i += bpp;
            decoded_px += run;
        }
    }

    ref_len_ = need;
    ref_pixel_count_ = pixel_count;
    ref_color_space_ = cs;
    have_ref_ = true;

    out.seq = seq;
    out.start_pixel = start_pixel;
    out.pixel_count = pixel_count;
    out.encoding = enc;
    out.color_space = cs;
    out.transfer = tf;
    out.payload = buf_;
    out.payload_len = need;
    return DecodeStatus::OK;
}

}  // namespace danmx
