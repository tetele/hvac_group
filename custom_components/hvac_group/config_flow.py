"""Add config flow for Blueprint."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast
import voluptuous as vol

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)

from .const import (
    CONF_CURRENT_TEMPERATURE_ENTITY_ID,
    CONF_COOLERS,
    CONF_HEATERS,
    CONF_TOGGLE_COOLERS,
    CONF_TOGGLE_HEATERS,
    DOMAIN,
)

OPTIONS_SCHEMA = {
    vol.Optional(CONF_HEATERS): selector.EntitySelector(
        selector.EntitySelectorConfig(domain=CLIMATE_DOMAIN, multiple=True),
    ),
    vol.Optional(CONF_TOGGLE_HEATERS): selector.BooleanSelector(),
    vol.Optional(CONF_COOLERS): selector.EntitySelector(
        selector.EntitySelectorConfig(domain=CLIMATE_DOMAIN, multiple=True),
    ),
    vol.Optional(CONF_TOGGLE_COOLERS): selector.BooleanSelector(),
    vol.Required(CONF_CURRENT_TEMPERATURE_ENTITY_ID): selector.EntitySelector(
        selector.EntityFilterSelectorConfig(domain=CLIMATE_DOMAIN)
    ),
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


class ClimateGroupConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
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
