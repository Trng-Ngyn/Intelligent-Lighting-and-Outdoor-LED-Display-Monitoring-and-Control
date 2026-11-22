#ifndef LIGHTING_CONTROL_FAULT_MANAGER_H
#define LIGHTING_CONTROL_FAULT_MANAGER_H
#include <string>
#include <vector>
#include "lighting_control/safety_decision.h"

namespace lighting {
class FaultManager {
public:
    void clear();
    void raise(const std::string& code, const std::string& level,
               const std::string& source, const std::string& description,
               bool recoverable, const std::string& timestamp);
    const std::vector<FaultInfo>& activeFaults() const;
private:
    std::vector<FaultInfo> faults_;
};
}  // namespace lighting
#endif
