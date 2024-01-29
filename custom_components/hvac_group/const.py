"""Constants for hvac_group integration."""
from logging import Logger, getLogger

DOMAIN = "hvac_group"
LOGGER: Logger = getLogger(__package__)

CONF_HVAC_MODES = "hvac_modes"
CONF_CURRENT_TEMPERATURE_ENTITY_ID = "temperature_entity_id"
CONF_COOLERS = "coolers"
CONF_HEATERS = "heaters"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_PRECISION = "precision"
CONF_TARGET_TEMP_HIGH = "target_temp_high"
CONF_TARGET_TEMP_LOW = "target_temp_low"
CONF_TARGET_TEMP_STEP = "target_temperature_step"
CONF_TOGGLE_COOLERS = "toggle_coolers"
CONF_TOGGLE_HEATERS = "toggle_heaters"
CONF_HIDE_MEMBERS = "hide_members"

VERSION = "0.1.1"
