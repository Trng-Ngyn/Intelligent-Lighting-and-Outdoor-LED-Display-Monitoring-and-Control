#ifndef LIGHTING_CONTROL_MODULE_RESULT_H
#define LIGHTING_CONTROL_MODULE_RESULT_H

#include <Arduino.h>

namespace lighting {
enum class ModuleStatus : uint8_t { SUCCESS, WARNING, ERROR };

// Hợp đồng gọn cho MCU: giữ đủ input/output, lỗi, chẩn đoán và timestamp.
// Python ModuleResult có cấu trúc JSON đầy đủ hơn cho log/simulator.
struct ModuleResult {
    const char* module;
    ModuleStatus status;
    const char* state;
    const char* error_code;
    const char* message;
    float input_value;
    float output_value;
    bool has_output;
    bool recoverable;
    const char* severity;
    const char* diagnostics;
    uint32_t timestamp_ms;

    ModuleResult(const char* module_name, ModuleStatus module_status,
                 const char* module_state, const char* code,
                 const char* error_message, float input, float output,
                 bool output_available, bool can_recover,
                 const char* error_severity = "MEDIUM",
                 const char* diagnostic_text = "")
        : module(module_name), status(module_status), state(module_state),
          error_code(code), message(error_message), input_value(input),
          output_value(output), has_output(output_available),
          recoverable(can_recover), severity(error_severity),
          diagnostics(diagnostic_text), timestamp_ms(millis()) {}
};
}  // namespace lighting
#endif
