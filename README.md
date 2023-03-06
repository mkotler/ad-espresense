# ad-espresense
Extend the capabilities of ESP Presense in Home Assistant using an  [AppDaemon](https://github.com/home-assistant/appdaemon) app.

Ad-Espresense will create a set of entities in Home Assistant corresponding to each of the devices that you want to track with ESPresense. Similar to using the mqtt_room platform in Home Assistant as defined in the [ESPresense Home Assistant documentation](https://espresense.com/home_assistant), the sensor's state will be the room the device is in.  However, it provides more flexibility and details to determine the location of the device.

Ad-Espresense listens for MQTT messages under the `espresense/devices/` topic.  For every device specified in the configuration file, it tracks proximity to each Base Station.  If no rooms are defined in the app configuration file then the application calculates the closest base station and records that in the state and then includes more details in the attributes. If rooms are defined, then the application calculates the closest room to the device.  

A detailed explanation of the sensor entities that are created is provided in the [Sensor Details](#sensor-details) section.  

## Getting Started

[Download](https://github.com/mkotler/ad-espresense) and copy the `espresense.py` file to your local `appdaemon\apps` directory, then add the appropriate app configuration to enable the `espresense` module.

This application relies on the MQTT Plugin for AppDaemon to listen to the MQTT messages from the ESPresense devices. Make sure that you have configured the MQTT Plug in the appdaemon.yaml file. See [Configuration of the MQTT Plugin](https://appdaemon.readthedocs.io/en/latest/CONFIGURE.html#configuration-of-the-mqtt-plugin) for details. I recommend specifying a `namespace` other than "default" in that configuration.

### Example App Configuration

Add your configuration to appdaemon/apps/apps.yaml as in the below example.  A table of all the configuration details is in the [Configuration Options](#configuration-options) section below. 

```yaml
espresense:
  module: espresense
  class: ESPresense
  debug: False
  log: espresense_log
  mqtt_namespace: mqtt
  devices:
    - { device_id: "irk:3a7b2c1d5e9f8a0b4c6d7e8f1a2b", entity_name: "matt_iphone" }
    - { device_id: "msft:cdp:8109", entity_name: "matt_desktop" }
  rooms:
    - { room: "office", main_bedroom: 5.47, playroom: 8.7, office: 3.39 }
    - { room: "family_room", main_bedroom: 2.49, playroom: 4.24, office: 5.92 }
    - { room: "kitchen", main_bedroom: 0.68, playroom: 4.06, office: 4.18 }
```

## Sensor Details

For each device specified in the app configuration file, an entity will be created in Home Assistant.  Note that the base stations are automatically captured from the topics under `espresense/devices/device_id/`. The sub-topic comes from the `Room` name as defined in the [ESPresense configuration](https://espresense.com/configuration/settings).

name | value
-- | --
Entity | The name of the entity is constructed by the `entity_prefix` in the app configuration file (`espresense` by default) and the `entity_name` in the list of devices. From the sample YAML above, two entities will be created, espresense.matt_iphone and espresense.matt_desktop. 
State | The base statation currently closest to the device. 
Attributes | An attribute is created for each base station and the value of the attribute is the distance from the device to that base station.   

## Configuration Options

key | optional | type | default | description
-- | -- | -- | -- | --
`module` | False | string | espresense | The module name of the app.
`class` | False | string | ESPresense | The name of the Class.
`debug` | True | bool | False | Determines whether to turn on logging. 
`log` | True | string | main_log | Specifies a custom log file name to use for logging.  Must be specified in appdaemon.yaml with both name and filename.  A [sample configuration](#sample-log-file-configuration) is provided below.
`mqtt_namespace` | True | string | default | Specifies the namespace used by the MQTT Plugin. Must be the same as what is in appdaemon.yaml.
`devices` | False | list | | List of devices for Espresense app to track. See details on the [device list](#devices) below.
`entity_prefix` | True | string | espresense | The prefix to use for the entity name.  For example, if `entity_prefix` is left as the default an entity name might be `espresense.device1`. Alternatively, if it is set to "espdevice" then it might be `espdevice.device1`.
`rooms` | True | list | | If provided the entity state will be represented by the room in this list with the closest proximty to the device.  See details on the [room list](#rooms) below.

### sample log file configuration
```yaml
  espresense_log:
    name: EspresenseLog
    filename: /config/appdaemon/logs/espresense.log
```

### devices
key | optional | type | default | description
-- | -- | -- | -- | --
`device_id` | False | string | | The fingerprint for the device to track. See any of the ESPresense [quick start guides](https://espresense.com/quick-start) on how to find the fingerprint. 
`entity_name` | False | string | | The entity name to use in Home Assistant to track this device.  For example, `matt_iphone` will be the entity espresense.matt_iphone.   

### rooms
key | optional | type | default | description
-- | -- | -- | -- | --
`room` | False | string | | Name of the room.
`base_stations` | False | float | | The other key, value pairs in this dictionary are names of base stations and the distance of the center of the room from that base station.  

For example, a room might look as follows: 
```yaml
- { room: "office", main_bedroom: 5.47, playroom: 8.7, office: 3.39 }
```
The name of the room is "office" and the center of the room is a distance of 5.47 from the main_bedroom base station, 8.7 from the playroom base station, and 3.39 from the office base station. The number of base stations in this list does not matter. You can determine these values either looking at the debug output of Ad-Espresense or by using a tool like MQTT explorer.  I recommend taking an average of values over a period of time.  