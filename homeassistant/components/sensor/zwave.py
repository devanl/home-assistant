"""
Interfaces with Z-Wave sensors.

For more details about this platform, please refer to the documentation
at https://home-assistant.io/components/sensor.zwave/
"""
import logging
import voluptuous as vol
# Because we do not compile openzwave on CI
# pylint: disable=import-error
from homeassistant.components.sensor import DOMAIN
from homeassistant.components import zwave
from homeassistant.const import ATTR_ENTITY_ID, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.components.zwave import async_setup_platform  # noqa # pylint: disable=unused-import
from homeassistant.helpers.service import extract_entity_ids
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_VALUE = 'value'

SENSOR_SET_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_VALUE): cv.byte,
})

SETTABLE_SENSORS = {}

def get_device(node, values, **kwargs):
    """Create Z-Wave entity device."""
    # Generic Device mappings
    if node.has_command_class(zwave.const.COMMAND_CLASS_INDICATOR):
        return ZWaveIndicatorSensor(values)
    if node.has_command_class(zwave.const.COMMAND_CLASS_SENSOR_MULTILEVEL):
        return ZWaveMultilevelSensor(values)
    if node.has_command_class(zwave.const.COMMAND_CLASS_METER) and \
            values.primary.type == zwave.const.TYPE_DECIMAL:
        return ZWaveMultilevelSensor(values)
    if node.has_command_class(zwave.const.COMMAND_CLASS_ALARM) or \
            node.has_command_class(zwave.const.COMMAND_CLASS_SENSOR_ALARM):
        return ZWaveAlarmSensor(values)
    return None

    
def setup_platform(hass, config, add_devices, discovery_info=None):

    def update(service):
        """Update service to set indicator values"""
        entity_ids = service.extract_entity_ids(hass, service)       
        value = service.data.get(ATTR_VALUE)
        
        if entity_ids and value:
        
          for sensor_id in entity_ids:
            if sensor_id in SETTABLE_SENSORS:
              SETTABLE_SENSORS[sensor_id].values.primary.data = int(value, 0)
            else:
              _LOGGER.error("Could not find settable entity for %s", sensor_id)
        else:
          _LOGGER.error("Missing attributes in servide call %r", service)
          return False

    hass.services.register(DOMAIN, 'set_indicator', update, schema=SENSOR_SET_SCHEMA)
    
    
class ZWaveIndicatorSensor(ZWaveSensor):
    def __init__(self, values, refresh, delay):
        """Initialize the light."""
        zwave.ZWaveDeviceEntity.__init__(self, values, DOMAIN)
        self._state = None
        self._delay = delay
        self._refresh_value = refresh
        
        # Used for value change event handling
        self._refreshing = False
        self._timer = None
        _LOGGER.debug('self._refreshing=%s self.delay=%s',
                      self._refresh_value, self._delay)
        self.value_added()
        self.update_properties()
        
        SETTABLE_SENSORS[self.entity_id] = self

    def update_properties(self):
        """Update internal properties based on zwave values."""
        self._state = self.values.primary.data
        
    def value_changed(self):
        """Call when a value for this entity's node has changed."""
        if self._refresh_value:
            if self._refreshing:
                self._refreshing = False
            else:
                def _refresh_value():
                    """Use timer callback for delayed value refresh."""
                    self._refreshing = True
                    self.values.primary.refresh()

                if self._timer is not None and self._timer.isAlive():
                    self._timer.cancel()

                self._timer = Timer(self._delay, _refresh_value)
                self._timer.start()
                return
        super().value_changed()

class ZWaveSensor(zwave.ZWaveDeviceEntity):
    """Representation of a Z-Wave sensor."""

    def __init__(self, values):
        """Initialize the sensor."""
        zwave.ZWaveDeviceEntity.__init__(self, values, DOMAIN)
        self.update_properties()

    def update_properties(self):
        """Handle the data changes for node values."""
        self._state = self.values.primary.data
        self._units = self.values.primary.units

    @property
    def force_update(self):
        """Return force_update."""
        return True

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement the value is expressed in."""
        return self._units


class ZWaveMultilevelSensor(ZWaveSensor):
    """Representation of a multi level sensor Z-Wave sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._units in ('C', 'F'):
            return round(self._state, 1)
        elif isinstance(self._state, float):
            return round(self._state, 2)

        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        if self._units == 'C':
            return TEMP_CELSIUS
        elif self._units == 'F':
            return TEMP_FAHRENHEIT
        return self._units


class ZWaveAlarmSensor(ZWaveSensor):
    """Representation of a Z-Wave sensor that sends Alarm alerts.

    Examples include certain Multisensors that have motion and vibration
    capabilities. Z-Wave defines various alarm types such as Smoke, Flood,
    Burglar, CarbonMonoxide, etc.

    This wraps these alarms and allows you to use them to trigger things, etc.

    COMMAND_CLASS_ALARM is what we get here.
    """

    pass
