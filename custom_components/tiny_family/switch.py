"""Switch entities for Tiny Family."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.restore_state import RestoreEntity


async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None
) -> None:
    """Set up the integration-owned compact mode switch."""
    async_add_entities([PersonTimelineCompactSwitch()])


class PersonTimelineCompactSwitch(SwitchEntity, RestoreEntity):
    """Control compact display across Tiny Family cards and dashboards."""

    _attr_icon = "mdi:view-compact"
    _attr_name = "Tiny Family compact"
    _attr_should_poll = False
    _attr_unique_id = "tiny_family_compact"

    def __init__(self) -> None:
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Restore the previous compact mode after a restart."""
        await super().async_added_to_hass()
        previous = await self.async_get_last_state()
        self._attr_is_on = previous is not None and previous.state == "on"

    async def async_turn_on(self, **kwargs) -> None:
        """Enable compact mode."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable compact mode."""
        self._attr_is_on = False
        self.async_write_ha_state()
