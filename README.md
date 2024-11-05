# HVAC Group

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]
[![SponsorMe][sponsormebadge]][sponsorme]

<!-- [![Discord][discord-shield]][discord] -->

[![Community Forum][forum-shield]][forum]

_Create a custom thermostat to control multiple other climate components. Useful for controlling an AC unit and a heating unit in a single room._

As it is, the integration is way behind the current HA version and is unlikely to work. It is advisable that you don't use it for now.

**This integration will set up the following platforms.**

| Platform  | Description                                                            |
| --------- | ---------------------------------------------------------------------- |
| `climate` | The replacement thermostat which can control other nested thermostats. |

The resulting thermostat will control all child members (heaters and coolers), but controlling a child won't propagate the change back to the group. The `hvac_action` of the group is not related directly to the `hvac_action` of the child members.

## Installation

### HACS

[![Open your Home Assistant instance and open HVAC Group inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=tetele&repository=hvac_group&category=Integration)

1. If you're using HACS, go to "HACS" > "Integrations" and search for the `HVAC Group` integration, then download it
1. In the HA UI go to "Settings" -> "Devices & services" -> "Helpers" click "+" and search for "HVAC Group"

## Configuration is done in the UI

1. Go to "Settings" -> "Devices & services" -> "Helpers" click "+ Create helper" and search for "HVAC group"
1. Name your new HVAC group. Something like `Bedroom climate`
1. Select one or more heating entities (e.g. the radiators and the electric heater in the bedroom)
1. Select one or more cooling entities (e.g. the air conditioning in the bedroom)
1. For both heaters and coolers, if you check `Toggle heaters/coolers on or off [...]`, they will physically be turned off if the desired temperature is reached
1. Select a climate entity or a temperature sensor which holds the current temperature (`Temperature sensor`)
1. If you check `Hide members`, creating the group will mark heater and cooler entities as hidden
1. Click `Submit`

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

---

[hvac_group]: https://github.com/tetele/hvac_group
[buymecoffee]: https://www.buymeacoffee.com/t3t3l3
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[sponsorme]: https://github.com/sponsors/tetele/
[sponsormebadge]: https://img.shields.io/badge/sponsor%20me-donate-yellow.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/tetele/hvac_group.svg?style=for-the-badge
[commits]: https://github.com/tetele/hvac_group/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge

<!-- [discord]: https://discord.gg/Qa5fW2R -->
<!-- [discord-shield]: https://img.shields.io/discord/330944238910963714.svg?style=for-the-badge -->
<!-- [exampleimg]: example.png -->

[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/tetele/hvac_group.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-Tudor%20Sandu%20%40tetele-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/tetele/hvac_group.svg?style=for-the-badge
[releases]: https://github.com/tetele/hvac_group/releases
