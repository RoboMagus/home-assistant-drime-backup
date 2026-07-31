# HomeAssistant Drime Backup integration

![Version](https://img.shields.io/github/v/release/RoboMagus/home-assistant-drime-backup?style=for-the-badge)
![License](https://img.shields.io/github/license/RoboMagus/home-assistant-drime-backup.svg?style=for-the-badge)

## About

This is a custom integration that allows HomeAssistant to upload backups to [Drime cloud](https://drime.cloud/) (not affiliated).

This custom component was developed to use the [Drime API](https://docs.drime.cloud/api-reference) to integrate with the cloud providers platform because [Drime does not (yet) support](https://www.reddit.com/r/Drime/comments/1ofgbje/comment/nl90pqj/) the [WebDav](https://www.home-assistant.io/integrations/webdav/) protocol.

## Why?

Drime offers GDPR compliant cloud storage hosted in the European Union. A way to be less relyant on the likes of Google, Amazon and Microslop.

At time of writing Drime offers 20GB free cloud storage and has lifetime storage deals for a decent price on StackSocial (bought **8TB** lifetime at **$220** myself). 20GB is plenty to just keep a few HA backups, and the lifetime multi-Terabyte plans make it interesting for offsite backups in a _3-2-1 Backup Strategy_.

As Drime supports [RClone](https://rclone.org/drime/), used in many popular backup services, most of the services hosted in my HomeLab are already backed-up to Drime cloud. This integration allows HomeAssistant backups to be uploaded to the same location directly from inside HomeAssistant.

## Installation

Install this component by clicking the button or following the manual instructions below:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=RoboMagus&repository=home-assistant-drime-backup&category=integration)

Follow [this guide](https://www.hacs.xyz/docs/faq/custom_repositories/) for installing custom repositories using HACS. For the URL of the repository use `https://github.com/RoboMagus/home-assistant-drime-backup` and for type select `Integration`.

### Configuration

After installation the integration must be configured. Do so by clicking the button or following the manual instructions below:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=drime)

1. Open the integrations dashboard (through `Settings > Devices & Services`)
2. Click `Add Integration` and search for `drime backup`
3. Provide required inputs and click `Submit`
   - The API key can be created in Drime settings under [Developers > API tokens](https://app.drime.cloud/account-settings#developers), by clicking `create token` under the `API access tokens` section. Be sure to select either `All` permissions, or write access to files and folders when choosing `Restricted`.
   - For Path select folder on Drime cloud storage where backups should be stored. If you run multiple HA instances be sure select different directories for each instance to avoid conflicts!
4. Configure additional options (gear icon)
   - Create storage sensors for extra paths

## Known Issues

1. **SLOW**: Drime cloud uploads [are quit slow](https://www.reddit.com/r/Drime/comments/1ubrlmg/horrible_upload_speed/). This appears to be caused by server side throttling and is not something that can be improved by this component.
2. **Space reclamation**: After a backup is deleted from Drime cloud, the size of the folder that holds the backups does not decrease. This is a server side issue that will hopefuly be resolved soon.
   - As the `Total size of backups` sensor reads the size of the directory, this size may differ from the sum of all sizes of individual backup files.

## Future Improvements

- [ ] Support non-default workspaces
- [ ] Implement proxy connection
- [ ] More sensors?

## Related work

Implementations of this custom component are based on the [Cloudflare R2](https://github.com/home-assistant/core/tree/dev/homeassistant/components/cloudflare_r2) core integration (as it is also uses S3 based file upload).

API implementations are inspired by [PyDrime](https://github.com/holgern/pydrime), but this library has not been used as it does not implement `async` methods preferred for HomeAssistant integrations.
