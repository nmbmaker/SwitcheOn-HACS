import base64
import binascii
import re
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import API_URL_STATUS, DOMAIN


class SwitcheOnConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            raw_url = user_input["qr_url"].strip()
            box_name = user_input.get("box_name", "My SwitcheOn").strip() or "My SwitcheOn"
            user_id_bin = user_input["user_id_bin"].strip()
            user_secret = user_input["user_secret"].strip()

            try:
                # 1. Extract 32-char hex token from full QR URL or raw hex string
                match = re.search(r"([0-9a-fA-F]{32})", raw_url)
                if not match:
                    raise ValueError("invalid_qr_link")
                hex_token = match.group(1).upper()

                # 2. Convert Hex to Base64 boxIdBin
                binary_data = binascii.unhexlify(hex_token)
                box_id_bin = base64.b64encode(binary_data).decode("utf-8")

            except ValueError as err:
                errors["base"] = str(err)
            except Exception:
                errors["base"] = "unknown"

            # 3. Prevent duplicate configuration of the same physical box
            if not errors:
                await self.async_set_unique_id(box_id_bin)
                self._abort_if_unique_id_configured()

                try:
                    # 4. Live API Verification (checks auth AND confirms box is linked)
                    session = async_get_clientsession(self.hass)
                    params = {
                        "UserIdBin": user_id_bin,
                        "UserSecret": user_secret,
                    }
                    async with session.get(API_URL_STATUS, params=params) as resp:
                        if resp.status != 200:
                            raise ValueError("invalid_auth")
                        data = await resp.json()
                        boxes = data.get("boxes") or []
                        if not any(b.get("boxIdBin") == box_id_bin for b in boxes):
                            raise ValueError("invalid_qr_link")

                    # 5. Store normalized credentials + custom device name
                    return self.async_create_entry(
                        title=box_name,
                        data={
                            "box_name": box_name,
                            "box_id_bin": box_id_bin,
                            "user_id_bin": user_id_bin,
                            "user_secret": user_secret,
                        },
                    )
                except ValueError as err:
                    errors["base"] = str(err)
                except Exception:
                    errors["base"] = "unknown"

        data_schema = vol.Schema({
            vol.Required("box_name", default="My SwitcheOn"): str,
            vol.Required("qr_url", description="Paste the SwitcheOn QR Link or 32-char Token"): str,
            vol.Required("user_id_bin", description="User ID Bin"): str,
            vol.Required("user_secret", description="User Secret"): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
