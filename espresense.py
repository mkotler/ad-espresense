"""ESPresense
   ESPresense enhancement via AppDaemon in Home Assistant
  @mkotler / https://github.com/mkotler/ad-espresense
"""
import mqttapi as mqtt
import json
from typing import Any

class ESPresense(mqtt.Mqtt):
    """ ESPresense class for listening to ESPresense MQTT messages and doing stuff """

    NAMESPACE = "default"
    ENTITY_PREFIX = "espresense"
    BASE_TOPIC = "espresense/devices/"
    DEBUG = False
    DEVICES: list = []
    RESET_EVENT = "espresense_reset"
    LOG_FILE = "main_log"

    def initialize(self) -> None:
        """Initialize ESPresense extension AppDaemon app """

        # Get whether to log debug 
        self.DEBUG = self.getarg('debug', self.DEBUG)
        self.LOG_FILE = self.getarg('log', self.LOG_FILE)
        self.lg("Initializing ESPresense application")

        # Load list of devices to track from config file
        self.DEVICES = self.getarg('devices', None)
        if self.DEVICES is None:
            self.lg("No devices were found to track")
            return
        
        # Get the namespace for the MQTT Plugin, specified in the app config
        self.NAMESPACE = self.getarg('mqtt_namespace', self.NAMESPACE)

        # Get the prefix for the sensor name to use
        self.ENTITY_PREFIX = self.getarg('entity_prefix', self.ENTITY_PREFIX)

        # Reset all devices to unavailable and clear attributes
        # and listen for reset event from Home Assistant
        self.reset()
        self.listen_event(self.reset_callback, event=self.RESET_EVENT)

        # Start listening for MQTT messages 
        try:
            self.listen_event(self.mqtt_callback,
                event="MQTT_MESSAGE",
                namespace=self.NAMESPACE)
        except Exception as ex:
            self.lg(ex)

    def lg(self, message) -> None:
        """Overidding log method below so only log if debug is true"""
        if self.DEBUG:
            self.log(message, log=self.LOG_FILE)

    def getarg(
        self,
        name: str,
        default: Any,
    ) -> Any:
        """Get configuration options from config file or use default"""
        if name in self.args:
            return self.args.pop(name)
        return default

    def mqtt_callback(self, event_name, data, kwargs):
        """Call back for when receive MQTT messages"""

        for device in self.DEVICES:
            lookup = self.BASE_TOPIC + device['device_id']
            # self.lg(lookup)

            # if the message is under the BASE_TOPIC path then continue
            if data['topic'].startswith(lookup):
                # Parse the json message
                room = data['topic'].split("/")[-1]
                payload = json.loads(data['payload'])
                distance = payload['distance']

                device_name = device['entity_name']
                entity_id = self.ENTITY_PREFIX + "." + device_name
                sensor_attr: dict[str, Any] = {}
                sensor_attr[room] = distance

                # look at all of the attributes (rooms) and pick the minimum value
                # if there aren't attributes yet, then just use current room
                try:
                    entity = self.get_entity(entity_id).get_state(attribute="all")
                    attributes = entity['attributes']
                    # self.lg(attributes)
                    min_room = min(attributes, key=attributes.get)
                except Exception:
                    min_room = room

                sensor_state = min_room

                self.set_state(
                    entity_id=entity_id,
                    state=sensor_state,
                    attributes=sensor_attr,
                )

                log_string = f"entity_id: {entity_id}, state: {sensor_state}, attributes: {sensor_attr}"
                self.lg(log_string)
                break

    def reset_callback(self, event: str, data: dict[str, str], _: dict[str, Any]) -> None:
        """Reset sensors when called from Home Assistant"""
        # To fire this event from Home Assistant go to Developer Tools | Events
        # In "Event Type" type the string value in self.RESET_EVENT (by default "espresense_report")
        self.lg("Reset event called")
        self.reset()

    def reset(self) -> None:
        """Resets sensors for all devices in configuration file"""
        for device in self.DEVICES:
            device_name = device['entity_name']
            entity_id = self.ENTITY_PREFIX + "." + device_name
            self.lg(f"Resetting state and removing attributes for {entity_id}")
            self.set_state(entity_id=entity_id, replace=True, state='unavailable', attributes={})
