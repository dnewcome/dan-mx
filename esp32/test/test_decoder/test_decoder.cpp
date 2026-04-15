// Host-side unit tests for the ESP32 decoder. Run with:
//   pio test -e native-test
//
// Validates the wire decoder against canned byte sequences matching the
// Python reference.

#include <unity.h>

#include <cstdint>
#include <cstring>
#include <vector>

#include "danmx.h"

namespace {

std::vector<uint8_t> header(danmx::EncodingMode enc, danmx::ColorSpace cs,
                            uint8_t seq, uint16_t start, uint16_t count) {
    std::vector<uint8_t> h = {
        'D', 'M', 'X', '2',
        1,                               // version
        0,                               // flags
        static_cast<uint8_t>(enc),
        static_cast<uint8_t>(cs),
        static_cast<uint8_t>(danmx::TransferFunction::LINEAR),
        seq,
        uint8_t(start >> 8), uint8_t(start & 0xFF),
        uint8_t(count >> 8), uint8_t(count & 0xFF),
    };
    return h;
}

}  // namespace

uint8_t g_buf[4096];

void setUp() {}
void tearDown() {}

void test_bytes_per_pixel() {
    TEST_ASSERT_EQUAL(3, danmx::bytes_per_pixel(danmx::ColorSpace::RGB888));
    TEST_ASSERT_EQUAL(2, danmx::bytes_per_pixel(danmx::ColorSpace::RGB565));
    TEST_ASSERT_EQUAL(2, danmx::bytes_per_pixel(danmx::ColorSpace::G6R5B5));
}

void test_bad_magic() {
    danmx::StreamDecoder d;
    d.init(g_buf, sizeof(g_buf));
    std::vector<uint8_t> pkt = {'X','X','X','X',1,0,0,0,0,0,0,0,0,1, 0,0,0};
    danmx::Frame f;
    TEST_ASSERT_EQUAL(int(danmx::DecodeStatus::BAD_MAGIC),
                      int(d.decode(pkt.data(), pkt.size(), f)));
}

void test_short() {
    danmx::StreamDecoder d;
    d.init(g_buf, sizeof(g_buf));
    std::vector<uint8_t> pkt = {'D','M','X','2',1};
    danmx::Frame f;
    TEST_ASSERT_EQUAL(int(danmx::DecodeStatus::SHORT_PACKET),
                      int(d.decode(pkt.data(), pkt.size(), f)));
}

void test_raw_roundtrip() {
    danmx::StreamDecoder d;
    d.init(g_buf, sizeof(g_buf));
    auto pkt = header(danmx::EncodingMode::RAW, danmx::ColorSpace::RGB888,
                      7, 0, 2);
    pkt.insert(pkt.end(), {0x11, 0x22, 0x33, 0x44, 0x55, 0x66});
    danmx::Frame f;
    TEST_ASSERT_EQUAL(int(danmx::DecodeStatus::OK),
                      int(d.decode(pkt.data(), pkt.size(), f)));
    TEST_ASSERT_EQUAL(7, f.seq);
    TEST_ASSERT_EQUAL(2, f.pixel_count);
    TEST_ASSERT_EQUAL(6, f.payload_len);
    TEST_ASSERT_EQUAL_HEX8(0x11, f.payload[0]);
    TEST_ASSERT_EQUAL_HEX8(0x66, f.payload[5]);
}

void test_rle_roundtrip() {
    danmx::StreamDecoder d;
    d.init(g_buf, sizeof(g_buf));
    // 5 pixels of (AA BB CC) RLE-compressed: [05][AA BB CC]
    auto pkt = header(danmx::EncodingMode::RLE, danmx::ColorSpace::RGB888,
                      0, 0, 5);
    pkt.insert(pkt.end(), {0x05, 0xAA, 0xBB, 0xCC});
    danmx::Frame f;
    TEST_ASSERT_EQUAL(int(danmx::DecodeStatus::OK),
                      int(d.decode(pkt.data(), pkt.size(), f)));
    TEST_ASSERT_EQUAL(15, f.payload_len);
    for (int i = 0; i < 5; ++i) {
        TEST_ASSERT_EQUAL_HEX8(0xAA, f.payload[i * 3 + 0]);
        TEST_ASSERT_EQUAL_HEX8(0xBB, f.payload[i * 3 + 1]);
        TEST_ASSERT_EQUAL_HEX8(0xCC, f.payload[i * 3 + 2]);
    }
}

void test_rle_run_of_256() {
    danmx::StreamDecoder d;
    d.init(g_buf, sizeof(g_buf));
    auto pkt = header(danmx::EncodingMode::RLE, danmx::ColorSpace::RGB888,
                      0, 0, 256);
    pkt.insert(pkt.end(), {0x00, 0x01, 0x02, 0x03});  // count=0 means 256
    danmx::Frame f;
    TEST_ASSERT_EQUAL(int(danmx::DecodeStatus::OK),
                      int(d.decode(pkt.data(), pkt.size(), f)));
    TEST_ASSERT_EQUAL(256 * 3, f.payload_len);
    TEST_ASSERT_EQUAL_HEX8(0x01, f.payload[0]);
    TEST_ASSERT_EQUAL_HEX8(0x03, f.payload[255 * 3 + 2]);
}

void test_delta_without_ref_returns_need_keyframe() {
    danmx::StreamDecoder d;
    d.init(g_buf, sizeof(g_buf));
    auto pkt = header(danmx::EncodingMode::DELTA, danmx::ColorSpace::RGB888,
                      0, 0, 1);
    pkt.insert(pkt.end(), {0x01, 0x00, 0x00, 0x00});
    danmx::Frame f;
    TEST_ASSERT_EQUAL(int(danmx::DecodeStatus::NEED_KEYFRAME),
                      int(d.decode(pkt.data(), pkt.size(), f)));
}

void test_delta_applied_against_prev() {
    danmx::StreamDecoder d;
    d.init(g_buf, sizeof(g_buf));

    // Keyframe: 2 pixels of (10, 20, 30)
    auto kf = header(danmx::EncodingMode::RLE, danmx::ColorSpace::RGB888, 0, 0, 2);
    kf.insert(kf.end(), {0x02, 10, 20, 30});
    danmx::Frame f;
    TEST_ASSERT_EQUAL(int(danmx::DecodeStatus::OK),
                      int(d.decode(kf.data(), kf.size(), f)));

    // Delta: XOR stream of (00,00,00) then (00,00,FF) — run-of-1 each.
    auto df = header(danmx::EncodingMode::DELTA, danmx::ColorSpace::RGB888, 1, 0, 2);
    df.insert(df.end(), {0x01, 0x00, 0x00, 0x00,  0x01, 0x00, 0x00, 0xFF});
    TEST_ASSERT_EQUAL(int(danmx::DecodeStatus::OK),
                      int(d.decode(df.data(), df.size(), f)));
    TEST_ASSERT_EQUAL_HEX8(10, f.payload[0]);
    TEST_ASSERT_EQUAL_HEX8(20, f.payload[1]);
    TEST_ASSERT_EQUAL_HEX8(30, f.payload[2]);
    TEST_ASSERT_EQUAL_HEX8(10, f.payload[3]);
    TEST_ASSERT_EQUAL_HEX8(20, f.payload[4]);
    TEST_ASSERT_EQUAL_HEX8(30 ^ 0xFF, f.payload[5]);
}

void test_overflow() {
    danmx::StreamDecoder d;
    uint8_t small[4];
    d.init(small, sizeof(small));
    auto pkt = header(danmx::EncodingMode::RAW, danmx::ColorSpace::RGB888, 0, 0, 10);
    pkt.insert(pkt.end(), 30, 0);
    danmx::Frame f;
    TEST_ASSERT_EQUAL(int(danmx::DecodeStatus::OVERFLOW_PIXELS),
                      int(d.decode(pkt.data(), pkt.size(), f)));
}

void test_g6r5b5_unpack_fields_dont_overlap() {
    // Pure red in G6R5B5 should unpack with zero green and zero blue.
    // Mirror the Python pack: v = ((g & 0xFC) << 8) | ((r & 0xF8) << 2) | (b >> 3)
    uint8_t r = 255, g = 0, b = 0;
    uint16_t v = ((g & 0xFC) << 8) | ((r & 0xF8) << 2) | (b >> 3);
    uint8_t packed[2] = {uint8_t(v >> 8), uint8_t(v & 0xFF)};
    uint8_t ur, ug, ub;
    danmx::unpack_pixel(danmx::ColorSpace::G6R5B5, packed, ur, ug, ub);
    TEST_ASSERT_EQUAL(0, ug);
    TEST_ASSERT_EQUAL(0, ub);
    TEST_ASSERT_TRUE(ur >= 248);
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_bytes_per_pixel);
    RUN_TEST(test_bad_magic);
    RUN_TEST(test_short);
    RUN_TEST(test_raw_roundtrip);
    RUN_TEST(test_rle_roundtrip);
    RUN_TEST(test_rle_run_of_256);
    RUN_TEST(test_delta_without_ref_returns_need_keyframe);
    RUN_TEST(test_delta_applied_against_prev);
    RUN_TEST(test_overflow);
    RUN_TEST(test_g6r5b5_unpack_fields_dont_overlap);
    return UNITY_END();
}
