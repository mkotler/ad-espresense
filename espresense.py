"""ESPresense
   ESPresense enhancement via AppDaemon in Home Assistant
  @mkotler / https://github.com/mkotler/ad-espresense
"""
import mqttapi as mqtt
import json
from typing import Any
import math

class ESPresense(mqtt.Mqtt):
    """ ESPresense class for listening to ESPresense MQTT messages and doing stuff """

    NAMESPACE = "default"
    ENTITY_PREFIX = "espresense"
    BASE_TOPIC = "espresense/devices/"
    DEBUG = False
    CONFIG = False
    DEVICES: list = []
    ROOMS: list = []
    HANDLES: list = {}
    RESET_EVENT = "espresense_reset"
    LOG_FILE = "main_log"
    MAX_DISTANCE = 16
    MESSAGE_TIMER = 60  # Max time between messages on a device before resetting a room

    def initialize(self) -> None:
        """Initialize ESPresense extension AppDaemon app """

        # Get whether to log debug 
        self.DEBUG = self.getarg('debug', self.DEBUG)
        self.CONFIG = self.getarg('config', self.CONFIG)
        self.LOG_FILE = self.getarg('log', self.LOG_FILE)
        self.lg("Initializing ESPresense application")

        # Load list of devices to track from config file
        devices = self.getarg('devices', None)
        if devices is None:
            self.lg("No devices were found to track")
            return

        # Save each device to the DEVICES list
        for device in devices:
            new_device = {
                'name': device['entity_name'], 
                'id': device['device_id'], 
                'base_stations': {}, 
                'room_distances': {} 
            }
            self.DEVICES.append(new_device)
            self.lg(f"Added device {new_device}")  # TODO: Remove extra logging

        # Get the namespace for the MQTT Plugin, specified in the app config
        self.NAMESPACE = self.getarg('mqtt_namespace', self.NAMESPACE)

        # Get the prefix for the sensor name to use
        self.ENTITY_PREFIX = self.getarg('entity_prefix', self.ENTITY_PREFIX)

        # Build a list of rooms, if they exist in the configuration
        self.ROOMS = self.getarg('rooms', None)

        # Reset all device sensors to unavailable and clear attributes
        # and listen for reset event from Home Assistant
        self.reset_sensors()
        self.listen_event(self.reset_callback, event=self.RESET_EVENT)

        # Start listening for MQTT messages 
        try:
            self.listen_event(self.mqtt_callback,
                event="MQTT_MESSAGE",
                namespace=self.NAMESPACE)
        except Exception as ex:
            self.lg(ex)

    def lg(self, message, config=False) -> None:
        """Overidding log method so only log if debug is true"""
        if self.CONFIG and not config:
            # If in configuration mode, only log items where parameter config=True
            return
        if self.DEBUG or self.CONFIG:
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
            # example device: 
            # {name: "matt_iphone", id: "irk:3a7b2c1d5e9f8a0b4c6d7e8f1a2b", 
            # base_stations: {bedroom: 1.54, office: 6.54}, 
            # room_distances: {kitchen: 3.23, family_room: 8.92}}

            device_name = device['name']
            lookup = self.BASE_TOPIC + device['id']

            # if the message is under the BASE_TOPIC path then continue
            if data['topic'].startswith(lookup):
                # Parse the json message
                base_station = data['topic'].split("/")[-1]
                payload = json.loads(data['payload'])
                distance = payload['distance']

                # cancel timers for this device and room
                self.clear_handle(device_name, base_station)

                # update the room distance
                # get the base stations

                base_stations = device['base_stations']
                base_stations[base_station] = distance
                self.update_room_distances(device)
                self.update_sensor(device)

                # Create callback to ensure that device receives another message 
                # from a base station within MESSAGE_TIMER
                self.lg(f"Starting timer for device: {device_name} and base station: {base_station}")
                handle = self.run_in(
                        self.clear_base_station, delay=self.MESSAGE_TIMER, device=device, base_station=base_station
                )
                self.add_handle(device_name, base_station, handle)

                # If CONFIG mode, log for calculating average distance for a device to a room
                if self.CONFIG:
                    log_string = f"|{base_station}|{distance}"
                    self.lg(log_string, True)

                break

    def add_handle(self, device_name, base_station, handle):
        """ Keep track of handles by device and room """
        self.HANDLES[(device_name, base_station)] = handle

    def clear_handle(self, device_name, base_station):
        """ Remove handle for a given device and room """
        handle = self.HANDLES.get((device_name, base_station))
        if handle is not None:
            if self.timer_running(handle):
                self.cancel_timer(handle)
                self.lg(f"Cancelling timer for device: {device_name} and base station: {base_station}")
            del self.HANDLES[(device_name, base_station)]

    def update_room_distances(self, device: Any):
        """ Update the room distances, based on base station distances """
        base_stations = device['base_stations']

        # Clear room distances
        device['room_distances'] = {}

        # base_distances is a dictionary of base stations with the value of each one being the distance
        # for example: { 'main_bedroom': X, 'playroom': Y, 'office': Z }

        # if no rooms have been defined only set room distances for each base station
        if self.ROOMS is None:
            for base_station in base_stations:
                device['room_distances'][base_station] = device['base_stations'][base_station]
        else:
            # compare the dict of distances against all of the rooms to find the closest room
            self.lg( f"Distance from {device['name']} to base stations: {base_stations}" )
            for room in self.ROOMS:
                # Calculate the distance between the target distances and each room
                # distance = self.euclidean_distance(device_distances, room)
                distance = self.law_of_cosines_average(base_stations, room)
                room_name = room['room']
                room_distances: dict = device['room_distances']
                self.lg(f"room_distances: {room_distances}")
                self.lg(f"room: {room_name}")
                self.lg(f"current_distance: {room_distances.get(room_name,'None')}")
                room_distances[room_name] = round(distance, 2)
            self.lg(f"Room distances: {device['room_distances']}")
    
    def update_sensor(self, device):
        """ Update the Home Assistant sensor for a passed in device """
        entity_id = self.ENTITY_PREFIX + "." + device['name']
        room_distances = device['room_distances']
        closest_room = (
            min(room_distances, key=room_distances.get)
            if (room_distances is not None and len(room_distances) != 0)
            else "unavailable"
        )

        self.set_state(
            entity_id=entity_id,
            state=closest_room,
            attributes=room_distances,
            replace=True
        )

        log_string = (
            f"Saving entity_id: {entity_id}, state: {closest_room}, attributes: {room_distances}"
        )
        self.lg(log_string)

    def reset_callback(self, event: str, data: dict[str, str], _: dict[str, Any]) -> None:
        """Reset sensors when called from Home Assistant"""
        # To fire this event from Home Assistant go to Developer Tools | Events
        # In "Event Type" type the string value in self.RESET_EVENT (by default "espresense_report")
        self.lg("Reset event called")
        self.reset_sensors()

    def reset_sensors(self) -> None:
        """Resets sensors for all devices in configuration file"""
        for device in self.DEVICES:
            device_name = device['name']
            entity_id = self.ENTITY_PREFIX + "." + device_name
            self.lg(f"Resetting state and removing attributes for {entity_id}")
            self.set_state(entity_id=entity_id, replace=True, state='unavailable', attributes={})
    
    def clear_base_station(self, kwargs: dict[str, Any] | None = None):
        """ Clears the base station a particular device  """
        device = kwargs.get("device", None)
        base_station = kwargs.get("base_station", None)

        if device['base_stations'][base_station] is not None:
            device['base_stations'].pop(base_station)

        # If haven't heard from that base station then also update
        # room distances and sensor
        self.update_room_distances(device)
        self.update_sensor(device)        

    def euclidean_distance(self, device_distances, room) -> float:
        # NOTE: This math is wrong
        # Calculate the Euclidean distance between the target distances and each room
        distance = 0
        for base_station, distance_from_base in device_distances.items():  
            if base_station in room:
                distance_to_add = (room[base_station] - distance_from_base)**2
            else:
                distance_to_add = (self.MAX_DISTANCE - distance_from_base)**2                 
            distance += distance_to_add
            self.lg(
                f"base_station: {base_station}, distance_from_base: {distance_from_base}, distance_to_add: {distance_to_add}" 
            )
        distance = distance**0.5
        # distance = sum([(room_distances[key] - distances[key])**2 for key in enumerate(distances.keys())])**0.5
        return distance

    def law_of_cosines_average(self, device_distances, room) -> float:
        # Calculate the distance using law of cosines and then take the average of the possible values
        # or if the values don't intersect, take the smallest of the largest possible values
        # law of cosines: c^2 = a^2+b^2-2ab*cos(C)
        max_distance_1 = 0
        min_distance_180 = float('inf') 

        for base_station, distance_from_base in device_distances.items():
            if base_station in room:
                room_distance = room[base_station]
            else:
                room_distance = self.MAX_DISTANCE             
            law_of_cosines_1 = (distance_from_base**2 + room_distance**2 - (2*distance_from_base*room_distance*math.cos(math.radians(1))))**0.5
            if max_distance_1 < law_of_cosines_1:
                max_distance_1 = law_of_cosines_1
            law_of_cosines_180 = (distance_from_base**2 + room_distance**2 - (2*distance_from_base*room_distance*math.cos(math.radians(180))))**0.5
            if min_distance_180 > law_of_cosines_180:
                min_distance_180 = law_of_cosines_180

        if max_distance_1 > min_distance_180:
            distance = min_distance_180
        else:
            distance = ((min_distance_180 - max_distance_1) / 2) + max_distance_1
            
        return distance
