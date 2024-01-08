"""Add config flow for Blueprint."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast
import voluptuous as vol

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers import entity_registry as er, selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)

from .const import (
    CONF_CURRENT_TEMPERATURE_ENTITY_ID,
    CONF_COOLERS,
    CONF_HEATERS,
    CONF_HIDE_MEMBERS,
    CONF_TOGGLE_COOLERS,
    CONF_TOGGLE_HEATERS,
    DOMAIN,
)

OPTIONS_SCHEMA = {
    vol.Optional(CONF_HEATERS, default=set()): selector.EntitySelector(
        selector.EntitySelectorConfig(domain=CLIMATE_DOMAIN, multiple=True),
    ),
    vol.Optional(CONF_TOGGLE_HEATERS): selector.BooleanSelector(),
    vol.Optional(CONF_COOLERS, default=set()): selector.EntitySelector(
        selector.EntitySelectorConfig(domain=CLIMATE_DOMAIN, multiple=True),
    ),
    vol.Optional(CONF_TOGGLE_COOLERS): selector.BooleanSelector(),
    vol.Required(CONF_CURRENT_TEMPERATURE_ENTITY_ID): selector.EntitySelector(
        selector.EntitySelectorConfig(
            filter=[
                selector.EntityFilterSelectorConfig(
                    domain=SENSOR_DOMAIN, device_class=SensorDeviceClass.TEMPERATURE
                ),
                selector.EntityFilterSelectorConfig(domain=CLIMATE_DOMAIN),
            ]
        )
    ),
    vol.Required(CONF_HIDE_MEMBERS, default=False): selector.BooleanSelector(),
}

CONFIG_SCHEMA = {
    vol.Required(CONF_NAME): selector.TextSelector(),
}

OPTIONS_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "init": SchemaFlowFormStep(vol.Schema(OPTIONS_SCHEMA))
}

CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "user": SchemaFlowFormStep(vol.Schema(CONFIG_SCHEMA).extend(OPTIONS_SCHEMA)),
}


class HvacGroupConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for HVAC Group."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    @callback
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title.

        The options parameter contains config entry options, which is the union of user
        input from the config flow steps.
        """
        return cast(str, options["name"]) if "name" in options else "HVAC Group"

    @callback
    def async_config_flow_finished(self, options: Mapping[str, Any]) -> None:
        """Hide the group members if requested."""
        if options[CONF_HIDE_MEMBERS]:
            _async_hide_actuators(
                self.hass,
                set().union(options[CONF_HEATERS], options[CONF_COOLERS]),
                er.RegistryEntryHider.INTEGRATION,
            )

    @callback
    @staticmethod
    def async_options_flow_finished(
        hass: HomeAssistant, options: Mapping[str, Any]
    ) -> None:
        """Hide or unhide the group members as requested."""
        hidden_by = (
            er.RegistryEntryHider.INTEGRATION if options[CONF_HIDE_MEMBERS] else None
        )
        _async_hide_actuators(
            hass, set().union(options[CONF_HEATERS], options[CONF_COOLERS]), hidden_by
        )


def _async_hide_actuators(
    hass: HomeAssistant, members: set[str], hidden_by: er.RegistryEntryHider | None
) -> None:
    """Hide or unhide group members."""
    registry = er.async_get(hass)
    for member in members:
        if not (entity_id := er.async_resolve_entity_id(registry, member)):
            continue
        if entity_id not in registry.entities:
            continue
        registry.async_update_entity(entity_id, hidden_by=hidden_by)
