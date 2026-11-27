/*
 * Lab-only Mosquitto 2.0 plugin (interface v5).
 *
 * Broker vẫn để retain_available true để status/LWT retained hoạt động, nhưng
 * policy này chỉ giữ retain trên nhánh status. Mọi PUBLISH tới topic khác bị
 * đổi thành non-retained trước khi broker lưu vào retained store.
 */

#include <stdbool.h>
#include <stddef.h>
#include <string.h>

#include <mosquitto.h>
#include <mosquitto_broker.h>
#include <mosquitto_plugin.h>

static bool retain_policy_allows(const char *topic)
{
	if(topic == NULL){
		return false;
	}

	/* Southbound: status/v1/{site}/{type}/{device} */
	if(strncmp(topic, "status/v1/", 10) == 0){
		return true;
	}

	/* Northbound: pccom/v1/{tenant}/{site}/{gateway}/status */
	if(strncmp(topic, "pccom/v1/", 9) == 0){
		const char *suffix = strstr(topic, "/status");
		if(suffix != NULL && suffix[7] == '\0'){
			return true;
		}
	}

	return false;
}

static int on_message(int event, void *event_data, void *userdata)
{
	struct mosquitto_evt_message *message = event_data;

	(void)event;
	(void)userdata;

	if(message == NULL){
		return MOSQ_ERR_INVAL;
	}

	if(message->retain && !retain_policy_allows(message->topic)){
		mosquitto_log_printf(MOSQ_LOG_WARNING,
				"pccom-retain: cleared retain on %s",
				message->topic != NULL ? message->topic : "(null)");
		message->retain = false;
	}

	return MOSQ_ERR_SUCCESS;
}

int mosquitto_plugin_version(int supported_version_count, const int *supported_versions)
{
	int i;

	for(i = 0; i < supported_version_count; i++){
		if(supported_versions[i] == 5){
			return 5;
		}
	}
	return -1;
}

int mosquitto_plugin_init(mosquitto_plugin_id_t *identifier, void **userdata,
		struct mosquitto_opt *options, int option_count)
{
	(void)userdata;
	(void)options;
	(void)option_count;

	return mosquitto_callback_register(identifier, MOSQ_EVT_MESSAGE,
			on_message, NULL, NULL);
}

int mosquitto_plugin_cleanup(void *userdata, struct mosquitto_opt *options,
		int option_count)
{
	(void)userdata;
	(void)options;
	(void)option_count;

	return MOSQ_ERR_SUCCESS;
}
