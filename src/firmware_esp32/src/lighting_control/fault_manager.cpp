#include "lighting_control/fault_manager.h"

namespace lighting {
void FaultManager::clear() { faults_.clear(); }

void FaultManager::raise(const std::string& code, const std::string& level,
                         const std::string& source, const std::string& description,
                         bool recoverable, const std::string& timestamp) {
    for (std::vector<FaultInfo>::iterator it = faults_.begin(); it != faults_.end(); ++it) {
        if (it->fault_code == code) {
            it->fault_level = level;
            it->source_module = source;
            it->description = description;
            it->recoverable = recoverable;
            it->timestamp = timestamp;
            it->active = true;
            return;
        }
    }
    FaultInfo fault;
    fault.fault_code = code;
    fault.fault_level = level;
    fault.source_module = source;
    fault.timestamp = timestamp;
    fault.description = description;
    fault.recoverable = recoverable;
    fault.active = true;
    faults_.push_back(fault);
}

const std::vector<FaultInfo>& FaultManager::activeFaults() const { return faults_; }
}  // namespace lighting
