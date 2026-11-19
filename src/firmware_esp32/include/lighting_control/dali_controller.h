#ifndef LIGHTING_CONTROL_DALI_CONTROLLER_H
#define LIGHTING_CONTROL_DALI_CONTROLLER_H

#include <Arduino.h>
#include "module_result.h"

namespace lighting {
enum class DaliAddressType : uint8_t { SHORT_ADDRESS, GROUP_ADDRESS, BROADCAST };
struct DaliAddress {
    DaliAddressType type;
    uint8_t value;
};
struct DaliDevice {
    const char* device_id;
    DaliAddress address;
    uint8_t min_level;
    uint8_t max_level;
};

// Adapter phần cứng phải triển khai timing/Manchester và transceiver DALI thật.
class IDaliBus {
public:
    virtual ~IDaliBus() {}
    virtual bool sendArcPower(const DaliAddress& address, uint8_t arc_level) = 0;
    virtual bool setFadeTime(const DaliAddress& address, uint8_t setting) = 0;
};

// Đường cong phần trăm -> arc power được tách riêng để khóa theo đặc tả Subtask 3.
class IArcPowerMapper {
public:
    virtual ~IArcPowerMapper() {}
    virtual bool map(float brightness_pct, const DaliDevice& device,
                     uint8_t& arc_level) const = 0;
};

class DaliDimmingController {
public:
    DaliDimmingController(IDaliBus& bus, const IArcPowerMapper& mapper);
    ModuleResult setBrightness(const DaliDevice& device, float brightness_pct);
    ModuleResult setFadeTime(const DaliDevice& device, uint8_t setting);
private:
    IDaliBus& bus_;
    const IArcPowerMapper& mapper_;
};
}  // namespace lighting
#endif
