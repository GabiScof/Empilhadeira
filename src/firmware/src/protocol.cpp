/**
 * protocol.cpp - Implementacao do framing JSON + CRC8 + '\n'.
 */
#include "protocol.h"

#include <ArduinoJson.h>
#include <string.h>

namespace {

constexpr uint8_t kCrc8ReflectedPolynomial = 0x8C;
constexpr char kFrameSeparator = '*';
constexpr char kFrameTerminator = '\n';
constexpr size_t kChecksumHexLen = 2;

bool isLowerHex(char value) {
  return (value >= '0' && value <= '9') || (value >= 'a' && value <= 'f');
}

void crcToLowerHex(uint8_t crc, char* out) {
  static constexpr char kHex[] = "0123456789abcdef";
  out[0] = kHex[(crc >> 4) & 0x0F];
  out[1] = kHex[crc & 0x0F];
}

size_t trimFrameEnd(const char* frame, size_t len) {
  while (len > 0 && (frame[len - 1] == '\n' || frame[len - 1] == '\r')) {
    --len;
  }
  return len;
}

bool splitAndValidateFrame(const char* frame,
                           size_t len,
                           const char*& payload,
                           size_t& payload_len) {
  if (frame == nullptr) {
    return false;
  }

  len = trimFrameEnd(frame, len);
  if (len <= kChecksumHexLen + 1) {
    return false;
  }

  size_t separator_index = len;
  for (size_t index = len; index > 0; --index) {
    if (frame[index - 1] == kFrameSeparator) {
      separator_index = index - 1;
      break;
    }
  }

  if (separator_index == len || separator_index == 0) {
    return false;
  }

  const size_t checksum_index = separator_index + 1;
  if (len - checksum_index != kChecksumHexLen) {
    return false;
  }

  const char checksum0 = frame[checksum_index];
  const char checksum1 = frame[checksum_index + 1];
  if (!isLowerHex(checksum0) || !isLowerHex(checksum1)) {
    return false;
  }

  payload = frame;
  payload_len = separator_index;

  char expected[2];
  crcToLowerHex(crc8(reinterpret_cast<const uint8_t*>(payload), payload_len), expected);
  return checksum0 == expected[0] && checksum1 == expected[1];
}

}  // namespace

const char* forkCommandToString(ForkCommand command) {
  switch (command) {
    case ForkCommand::SUBIR:
      return "subir";
    case ForkCommand::DESCER:
      return "descer";
    case ForkCommand::PARAR:
    default:
      return "parar";
  }
}

bool forkCommandFromString(const char* value, ForkCommand& out) {
  if (value == nullptr) {
    return false;
  }
  if (strcmp(value, "subir") == 0) {
    out = ForkCommand::SUBIR;
    return true;
  }
  if (strcmp(value, "descer") == 0) {
    out = ForkCommand::DESCER;
    return true;
  }
  if (strcmp(value, "parar") == 0) {
    out = ForkCommand::PARAR;
    return true;
  }
  return false;
}

uint8_t crc8(const uint8_t* data, size_t len) {
  uint8_t crc = 0x00;
  if (data == nullptr) {
    return crc;
  }

  for (size_t index = 0; index < len; ++index) {
    crc ^= data[index];
    for (uint8_t bit = 0; bit < 8; ++bit) {
      if ((crc & 0x01) != 0) {
        crc = static_cast<uint8_t>((crc >> 1) ^ kCrc8ReflectedPolynomial);
      } else {
        crc = static_cast<uint8_t>(crc >> 1);
      }
    }
  }

  return crc;
}

bool decodeSetpoint(const char* frame, size_t len, Setpoint& out) {
  const char* payload = nullptr;
  size_t payload_len = 0;
  if (!splitAndValidateFrame(frame, len, payload, payload_len)) {
    return false;
  }

  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, payload, payload_len);
  if (error) {
    return false;
  }

  if (!doc["w_esq"].is<float>() || !doc["w_dir"].is<float>()) {
    return false;
  }

  const char* garfo_value = doc["garfo"].as<const char*>();
  ForkCommand garfo = ForkCommand::PARAR;
  if (!forkCommandFromString(garfo_value, garfo)) {
    return false;
  }

  Setpoint parsed;
  parsed.w_esq = doc["w_esq"].as<float>();
  parsed.w_dir = doc["w_dir"].as<float>();
  parsed.garfo = garfo;
  out = parsed;
  return true;
}

size_t encodeSensors(const Sensors& sensors, char* out, size_t out_size) {
  if (out == nullptr || out_size == 0) {
    return 0;
  }

  JsonDocument doc;
  JsonObject enc = doc["enc"].to<JsonObject>();
  enc["esq"] = sensors.enc_esq;
  enc["dir"] = sensors.enc_dir;

  JsonObject mpu = doc["mpu"].to<JsonObject>();
  mpu["ax"] = sensors.ax;
  mpu["ay"] = sensors.ay;
  mpu["az"] = sensors.az;
  mpu["gx"] = sensors.gx;
  mpu["gy"] = sensors.gy;
  mpu["gz"] = sensors.gz;
  mpu["temp_c"] = sensors.mpu_temp_c;

  if (sensors.has_bms) {
    JsonObject bms = doc["bms"].to<JsonObject>();
    bms["cel"] = sensors.bms_cel;        // TODO(equipe): confirmar unidade de cel (V?)
    bms["i_a"] = sensors.bms_i_a;        // A
    bms["temp_c"] = sensors.bms_temp_c;  // graus C
  } else {
    doc["bms"] = nullptr;
  }

  const size_t payload_len = measureJson(doc);
  const size_t frame_len = payload_len + 1 + kChecksumHexLen + 1;
  if (frame_len > out_size) {
    return 0;
  }

  const size_t written = serializeJson(doc, out, out_size);
  if (written != payload_len) {
    return 0;
  }

  const uint8_t checksum = crc8(reinterpret_cast<const uint8_t*>(out), payload_len);
  out[payload_len] = kFrameSeparator;
  crcToLowerHex(checksum, &out[payload_len + 1]);
  out[payload_len + 1 + kChecksumHexLen] = kFrameTerminator;

  if (frame_len < out_size) {
    out[frame_len] = '\0';
  }

  return frame_len;
}

SetpointFrameDecoder::SetpointFrameDecoder(char* buffer, size_t capacity)
    : buffer_(buffer), capacity_(capacity), len_(0), dropping_(false) {}

bool SetpointFrameDecoder::push(uint8_t byte, Setpoint& out) {
  if (byte == static_cast<uint8_t>(kFrameTerminator)) {
    const bool was_dropping = dropping_;
    dropping_ = false;

    if (was_dropping) {
      len_ = 0;
      return false;
    }

    const bool decoded = decodeSetpoint(buffer_, len_, out);
    len_ = 0;
    return decoded;
  }

  if (byte == static_cast<uint8_t>('\r')) {
    return false;
  }

  if (dropping_) {
    return false;
  }

  if (buffer_ == nullptr || capacity_ == 0 || len_ >= capacity_) {
    dropping_ = true;
    len_ = 0;
    return false;
  }

  buffer_[len_] = static_cast<char>(byte);
  ++len_;
  return false;
}

void SetpointFrameDecoder::reset() {
  len_ = 0;
  dropping_ = false;
}

size_t SetpointFrameDecoder::pending() const {
  return len_;
}

bool SetpointFrameDecoder::dropping() const {
  return dropping_;
}
