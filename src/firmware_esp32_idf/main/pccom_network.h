#ifndef PCCOM_NETWORK_H
#define PCCOM_NETWORK_H

#include "pccom_config.h"

/* Network Manager task: WiFi + SNTP + mTLS MQTT 5, giữ LWT và là nơi duy nhất
 * gọi esp_mqtt_client_publish(). Không subscribe bất kỳ topic nào ở S2. */
void pccom_network_task(void *arg);

#endif /* PCCOM_NETWORK_H */
