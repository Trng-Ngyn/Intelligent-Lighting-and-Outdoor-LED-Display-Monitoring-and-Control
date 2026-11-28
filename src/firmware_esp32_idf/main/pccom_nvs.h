#ifndef PCCOM_NVS_H
#define PCCOM_NVS_H

#include <stdbool.h>
#include <stdint.h>

#include "esp_err.h"
#include "pccom_config.h"

esp_err_t pccom_nvs_init(void);
bool pccom_nvs_has_config(void);
esp_err_t pccom_nvs_load(pccom_config_t *cfg);
esp_err_t pccom_nvs_save(const pccom_config_t *cfg);
esp_err_t pccom_nvs_next_sequence(uint32_t *sequence);

#endif /* PCCOM_NVS_H */
