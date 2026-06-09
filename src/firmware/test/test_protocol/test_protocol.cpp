#include <unity.h>
#include "protocol.h"
#include <string.h>

// ── CRC ──────────────────────────────────────────────────────────────
void test_crc8_known_setpoint() {
    const char* payload = "{\"w_esq\":1.5,\"w_dir\":1.5,\"garfo\":\"parar\"}";
    TEST_ASSERT_EQUAL_HEX8(0x6e, crc8((const uint8_t*)payload, strlen(payload)));
}

void test_crc8_sensors_frame() {
    const char* payload = "{\"enc\":{\"esq\":1.5,\"dir\":1.5},\"mpu\":{\"ax\":0,\"ay\":0,\"az\":9.81,\"gx\":0,\"gy\":0,\"gz\":0,\"temp_c\":25},\"bms\":null}";
    TEST_ASSERT_EQUAL_HEX8(0xd5, crc8((const uint8_t*)payload, strlen(payload)));
}

void test_crc8_empty() {
    TEST_ASSERT_EQUAL_HEX8(0x00, crc8(nullptr, 0));
}

// ── decodeSetpoint ────────────────────────────────────────────────────
void test_decode_setpoint_valido() {
    const char frame[] = "{\"w_esq\":1.5,\"w_dir\":1.5,\"garfo\":\"parar\"}*6e\n";
    Setpoint sp;
    TEST_ASSERT_TRUE(decodeSetpoint(frame, sizeof(frame) - 1, sp));
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 1.5f, sp.w_esq);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 1.5f, sp.w_dir);
    TEST_ASSERT_EQUAL(ForkCommand::PARAR, sp.garfo);
}

void test_decode_setpoint_parado() {
    const char frame[] = "{\"w_esq\":0.0,\"w_dir\":0.0,\"garfo\":\"parar\"}*5e\n";
    Setpoint sp;
    TEST_ASSERT_TRUE(decodeSetpoint(frame, sizeof(frame) - 1, sp));
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 0.0f, sp.w_esq);
}

void test_decode_setpoint_giro_subir() {
    const char frame[] = "{\"w_esq\":-1.0,\"w_dir\":1.0,\"garfo\":\"subir\"}*df\n";
    Setpoint sp;
    TEST_ASSERT_TRUE(decodeSetpoint(frame, sizeof(frame) - 1, sp));
    TEST_ASSERT_FLOAT_WITHIN(0.001f, -1.0f, sp.w_esq);
    TEST_ASSERT_EQUAL(ForkCommand::SUBIR, sp.garfo);
}

void test_decode_setpoint_crc_errado() {
    const char frame[] = "{\"w_esq\":1.5,\"w_dir\":1.5,\"garfo\":\"parar\"}*ff\n";
    Setpoint sp;
    TEST_ASSERT_FALSE(decodeSetpoint(frame, sizeof(frame) - 1, sp));
}

void test_decode_setpoint_sem_separador() {
    const char frame[] = "{\"w_esq\":1.5,\"w_dir\":1.5,\"garfo\":\"parar\"}\n";
    Setpoint sp;
    TEST_ASSERT_FALSE(decodeSetpoint(frame, sizeof(frame) - 1, sp));
}

void test_decode_setpoint_payload_vazio() {
    const char frame[] = "*6e\n";
    Setpoint sp;
    TEST_ASSERT_FALSE(decodeSetpoint(frame, sizeof(frame) - 1, sp));
}

// ── SetpointFrameDecoder ──────────────────────────────────────────────
void test_decoder_frame_inteiro() {
    char buf[256];
    SetpointFrameDecoder dec(buf, sizeof(buf));
    const char frame[] = "{\"w_esq\":1.5,\"w_dir\":1.5,\"garfo\":\"parar\"}*6e\n";
    Setpoint sp;
    bool got = false;
    for (size_t i = 0; i < strlen(frame); i++) {
        if (dec.push((uint8_t)frame[i], sp)) got = true;
    }
    TEST_ASSERT_TRUE(got);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 1.5f, sp.w_esq);
}

void test_decoder_frame_corrompido_descarta() {
    char buf[256];
    SetpointFrameDecoder dec(buf, sizeof(buf));
    const char bad[]   = "lixo_corrompido*ff\n";
    const char good[]  = "{\"w_esq\":1.5,\"w_dir\":1.5,\"garfo\":\"parar\"}*6e\n";
    Setpoint sp;
    bool got = false;
    for (size_t i = 0; i < strlen(bad);  i++) dec.push((uint8_t)bad[i],  sp);
    for (size_t i = 0; i < strlen(good); i++) if (dec.push((uint8_t)good[i], sp)) got = true;
    TEST_ASSERT_TRUE(got);
}

// Remova o main() e coloque:
void setup() {
    UNITY_BEGIN();
    RUN_TEST(test_crc8_known_setpoint);
    RUN_TEST(test_crc8_sensors_frame);
    RUN_TEST(test_crc8_empty);
    RUN_TEST(test_decode_setpoint_valido);
    RUN_TEST(test_decode_setpoint_parado);
    RUN_TEST(test_decode_setpoint_giro_subir);
    RUN_TEST(test_decode_setpoint_crc_errado);
    RUN_TEST(test_decode_setpoint_sem_separador);
    RUN_TEST(test_decode_setpoint_payload_vazio);
    RUN_TEST(test_decoder_frame_inteiro);
    RUN_TEST(test_decoder_frame_corrompido_descarta);
    UNITY_END();
}

void loop() {}