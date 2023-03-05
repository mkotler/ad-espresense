"""ESPresense
   ESPresense enhancement via AppDaemon in Home Assistant
  @mkotler / https://github.com/mkotler/ad-espresense
"""
import mqttapi as mqtt
import json
from typing import Any

class ESPresense(mqtt.Mqtt):
    """ ESPresense class for listening to ESPresense MQTT messages and doing stuff """

    entity_prefix = "espresense."
    base_topic = "espresense/devices/"
    debug = False
    devices: list = []
    reset_event = "espresense_reset"

    def initialize(self) -> None:
        """Initialize ESPresense extension AppDaemon app """

        # Get whether to log debug 
        self.debug = self.args.pop('debug')
        self.lg("Initializing ESPresense application")

        # Listen for reset event to clear all sensors
        self.listen_event(self.reset, event=self.reset_event)

        # Load list of devices to track from config file
        self.devices = self.args.pop('devices')

        # Start listening for MQTT messages 
        try:
            self.listen_event(self.mqtt_callback,
                event="MQTT_MESSAGE",
                namespace="mqtt")
        except Exception as ex:
            self.lg(ex)

    def lg(self, message) -> None:
        """Overidding log method below so only log if debug is true"""
        if self.debug:
            self.log(message)

    def mqtt_callback(self, event_name, data, kwargs):
        """Call back for when receive MQTT messages"""

        for device in self.devices:
            lookup = self.base_topic + device['device_id']
            # self.lg(lookup)

            # if the message is under the base_topic path then continue
            if data['topic'].startswith(lookup):
                # Parse the json message
                room = data['topic'].split("/")[-1]
                payload = json.loads(data['payload'])
                distance = payload['distance']

                device_name = device['entity_name']
                entity_id = self.entity_prefix + device_name
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

    def reset(self, event: str, data: dict[str, str], _: dict[str, Any]) -> None:
        """Remove all of the sensors associated with epresense to reset to clean state"""
        # To fire this event from Home Assistant go to Developer Tools | Events
        # In "Event Type" type the string value in self.reset_event (by default "espresense_report")
        for device in self.devices:
            device_name = device['entity_name']
            entity_id = self.entity_prefix + device_name
            self.remove_entity(entity_id)