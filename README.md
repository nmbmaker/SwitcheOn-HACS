# SwitcheOn Custom Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![version](https://img.shields.io/badge/version-1.3.0-blue.svg)](https://github.com/nmbmaker/SwitcheOn-HACS/releases)

An unofficial Home Assistant custom integration for [SwitcheOn](https://switcheon.com/) LTE-M / NB-IoT cellular remote power switches and cellular thermostats. Control aircraft engine preheaters, hangar lights, battery tenders, and remote equipment directly from Home Assistant—with zero manual token extraction or proxy sniffing required.

---

## Features

- **Zero-Credential QR Setup:** Upload a screenshot or snap a mobile camera photo of your SwitcheOn QR code during setup. Home Assistant automatically generates and registers its own isolated device credentials in the background.
- **2-Channel, 4-Channel & Thermostat Support:** Dynamically detects your box model (`2-Channel`, `4-Channel`, or `Cellular Thermostat`), respects 15A High Power mutually exclusive relay configurations, and tracks in-flight cellular `pendingStatus` transitions so switches don't bounce while waiting for LTE-M confirmation.
- **Collision-Free Switching:** Performs a live pre-command cloud sync before toggling relays so changes made concurrently in the SwitcheOn mobile app are never overwritten.
- **Multi-Box Friendly Entity Naming:** Clean, predictable entity IDs (`switch.switcheon_<device_name>_sw0`, `sw1`, etc.) so multiple hangar or remote boxes never collide, paired with live friendly channel names pulled from the SwitcheOn app.
- **Manual Refresh & Configurable Polling:** Includes a dedicated **Refresh** button entity for on-demand updates plus an integration **Configure** menu to adjust polling between 15 and 600 seconds.
- **Ambient Temperature Monitoring:** Live temperature sensor respecting your box's Fahrenheit/Celsius setting with long-term statistics graphing.
- **Built-In Backup QR Code (`image`):** Generates a scannable QR code right on the Home Assistant device page—making it easy to pair a new phone or share access without climbing behind hangar equipment.
- **Subscription Renewal & Cellular Diagnostics:** Tracks your box's `paidUntil` renewal date, auto-renew status, LTE-M signal strength (dBm), online connectivity state, in-flight command status, last cellular check-in timestamp, redacted diagnostics export, and automatic cloud user cleanup on removal.

---

## Entities Created

Assuming a Device Name of `N12345` during setup:

| Platform | Entity ID | Description |
| :--- | :--- | :--- |
| `switch` | `switch.switcheon_n12345_sw0` .. `sw3` | Individual relay controls (2 or 4 channels depending on model) |
| `button` | `button.switcheon_n12345_refresh` | Triggers an immediate cloud status refresh |
| `sensor` | `sensor.switcheon_n12345_temperature` | Ambient temperature reading (`°F` or `°C`) |
| `sensor` | `sensor.switcheon_n12345_signal_strength` | Cellular LTE-M signal strength (`dBm`) |
| `sensor` | `sensor.switcheon_n12345_renewal_date` | Annual cellular service expiration/renewal date (`YYYY-MM-DD`) |
| `sensor` | `sensor.switcheon_n12345_last_checkin` | Timestamp of the box's most recent cloud check-in |
| `binary_sensor` | `binary_sensor.switcheon_n12345_cellular_status` | Online / Offline connectivity status (+ IMEI, ICCID & schedule attributes) |
| `binary_sensor` | `binary_sensor.switcheon_n12345_command_pending` | `On` while a cellular switch or HVAC command is awaiting confirmation |
| `image` | `image.switcheon_n12345_qr_code` | Scannable activation QR code (+ raw activation URL attribute) |
| `climate` | `climate.switcheon_n12345_thermostat` | Created automatically only on SwitcheOn Cellular Thermostat models |

---

## Installation

### Option 1: HACS (Recommended)

1. Open **HACS** in Home Assistant.
2. Click the three-dot menu (**⋮**) in the top-right corner and select **Custom repositories**.
3. Paste `https://github.com/nmbmaker/SwitcheOn-HACS` into the repository field, select **Integration** as the category, and click **Add**.
4. Locate **SwitcheOn** in HACS and click **Download**.
5. Restart Home Assistant (**Developer Tools** -> **YAML** -> **Restart**).

### Option 2: Manual Installation

1. Download the latest release from this repository.
2. Copy the `custom_components/switcheon` folder into your Home Assistant `/config/custom_components/` directory.
3. Restart Home Assistant.

---

## Setup & Configuration

1. In Home Assistant, navigate to **Settings** -> **Devices & Services** and click **+ Add Integration**.
2. Search for and select **SwitcheOn**.
3. Fill in the setup prompt:
   - **Device Name:** Enter an identifier for this box (for example, `N12345` or `North Hangar`).
   - **SwitcheOn QR Code Image:** Upload a screenshot of the QR code from your SwitcheOn mobile app (or snap a clear photo of the physical QR sticker on the box using the Home Assistant mobile app).
4. Click **Submit**. Home Assistant will register itself (appearing as `Home Assistant` in your SwitcheOn app's user list), link the box, and create all entities automatically.
5. *(Optional)* Click **Configure** on the integration entry at any time to adjust the cloud polling interval (15–600 seconds), and update `translations/en.json` or `config_flow.py` example text if you also want `N12345` shown inside the Home Assistant setup prompt.

> **Adding Additional Boxes:** Simply click **Add Entry** under the SwitcheOn integration card and upload the next box's QR code. Home Assistant will automatically reuse its local SwitcheOn identity across all of your boxes.

---

## Notes on Cellular Operation

**Command Latency:** SwitcheOn boxes communicate over low-power LTE-M / NB-IoT cellular networks. When you toggle a switch in Home Assistant, the switch immediately enters an optimistic pending state (tracked by the `command_pending` binary sensor) while the cellular network wakes the relay (typically 3–15 seconds).

**Polling Interval:** Cloud state is polled every 60 seconds by default (configurable between 15 and 600 seconds under **Configure**), with a live sync performed before every command and on-demand via the **Refresh** button.

**Channel Renaming:** Friendly switch names dynamically follow the channel labels configured in your SwitcheOn mobile app while keeping your underlying `switch.switcheon_<device>_sw0` entity IDs unchanged so automations never break.

---

**Disclaimer**

This project is an independent community integration and is not affiliated with, endorsed by, or supported by SwitcheOn. Always follow manufacturer electrical load limits (15A max) and aviation/hangar safety guidelines when operating unattended preheating equipment.

---

## Example Automation: Annual Renewal Reminder

Because `sensor.switcheon_<device>_renewal_date` uses Home Assistant's native `date` device class (and exposes an `auto_renew` attribute), you can trigger a mobile notification 14 days before your cellular subscription expires—especially helpful if a credit card expires and auto-renew turns off, please be sure to change the example sensors to your specific ones:

```yaml
alias: "Hangar SwitcheOn - Cellular Renewal Reminder"
description: "Notify 14 days before the SwitcheOn cellular plan expires"
triggers:
  - trigger: time
    at: "09:00:00"
conditions:
  - condition: template
    value_template: >
      {% set renewal = states('sensor.switcheon_n12345_renewal_date') | as_datetime | as_local %}
      {{ (renewal.date() - now().date()).days == 14 }}
actions:
  - action: notify.mobile_app_your_phone
    data:
      title: "SwitcheOn Renewal Approaching"
      message: >
        SwitcheOn N12345 service expires on {{ states('sensor.switcheon_n12345_renewal_date') }}.
        Status: {{ state_attr('sensor.switcheon_n12345_renewal_date', 'subscription_info') }}
