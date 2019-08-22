"""Support for Honeywell Lyric devices."""
import logging
from typing import Any, Dict

import voluptuous as vol
from lyric import Lyric

from homeassistant.const import CONF_TOKEN
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from .const import (DATA_LYRIC_CLIENT, DOMAIN,
                    CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_LYRIC_CONFIG_FILE,
                    DATA_LYRIC_CONFIG, SERVICE_HOLD_TIME)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the Lyric component."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    # Store config to be used during entry setup
    hass.data[DATA_LYRIC_CONFIG] = conf

    return True


async def async_setup_entry(
        hass: HomeAssistantType, entry: ConfigEntry
) -> bool:
    """Set up Lyric from a config entry."""
    conf = hass.data[DATA_LYRIC_CONFIG]

    client_id = conf[CONF_CLIENT_ID]
    client_secret = conf[CONF_CLIENT_SECRET]
    token = entry.data[CONF_TOKEN]
    token_cache_file = hass.config.path(CONF_LYRIC_CONFIG_FILE)

    lyric = Lyric(app_name='Home Assistant', client_id=client_id,
                  client_secret=client_secret,
                  token=token, token_cache_file=token_cache_file)

    hass.data.setdefault(DOMAIN, {})[DATA_LYRIC_CLIENT] = LyricClient(lyric)

    for component in 'climate', 'sensor':
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(
        hass: HomeAssistantType, entry: ConfigType
) -> bool:
    """Unload Lyric config entry."""
    for component in 'climate', 'sensor':
        await hass.config_entries.async_forward_entry_unload(entry, component)

    # Remove the climate service
    hass.services.async_remove(DOMAIN, SERVICE_HOLD_TIME)

    del hass.data[DOMAIN]

    return True


class LyricClient:
    """Structure Lyric functions for hass."""

    def __init__(self, lyric):
        """Init Lyric devices."""
        self.lyric = lyric

        if not lyric.locations:
            return

        self._location = [location.name for location in lyric.locations]

    def devices(self):
        """Generate a list of thermostats and their location."""
        try:
            for location in self.lyric.locations:
                if location.name in self._location:
                    for device in location.thermostats:
                        yield (location, device)
                else:
                    _LOGGER.debug("Ignoring location %s, not in %s",
                                  location.name, self._location)
        except ConnectionError:
            _LOGGER.error(
                "Connection error logging into the Lyric web service.")


class LyricEntity(Entity):
    """Defines a base Lyric entity."""

    def __init__(self, device, location,
                 unique_id: str, name: str,
                 icon: str, device_class: str) -> None:
        """Initialize the Lyric entity."""
        self._unique_id = unique_id
        self._name = name
        self._icon = icon
        self._device_class = device_class
        self._available = False
        self.device = device
        self.location = location

    @property
    def unique_id(self) -> str:
        """Return unique ID for the sensor."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def device_class(self) -> str:
        """Return the class of this device."""
        return self._device_class

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    async def async_update(self) -> None:
        """Update Lyric entity."""
        await self._lyric_update()
        self._available = True

    async def _lyric_update(self) -> None:
        """Update Lyric entity."""
        raise NotImplementedError()


class LyricDeviceEntity(LyricEntity):
    """Defines a Lyric device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this Lyric instance."""
        mac_address = self.device.macID
        return {
            'identifiers': {
                (
                    DOMAIN,
                    mac_address
                )
            },
            'name': self.device.name,
            'model': self.device.id,
            'manufacturer': 'Honeywell'
        }
