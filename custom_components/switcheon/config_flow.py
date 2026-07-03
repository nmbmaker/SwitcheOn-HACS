import voluptuous as vol
import base64
import binascii
import aiohttp
from homeassistant import config_entries
from .const import DOMAIN, API_URL_STATUS

class SwitcheOnConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            raw_url = user_input["qr_url"]
            box_name = user_input.get("box_name", "My SwitcheOn")
            
            try:
                # 1. Extract Token
                url = raw_url.upper().strip()
                hex_token = url.split("ACT/")[1] if "ACT/" in url else url
                
                if len(hex_token) != 32:
                    raise ValueError("invalid_qr_link")

                # 2. Convert Hex to Base64
                binary_data = binascii.unhexlify(hex_token)
                box_id_bin = base64.b64encode(binary_data).decode('utf-8')

            except ValueError as e:
                errors["base"] = str(e)
            except Exception:
                errors["base"] = "unknown"

            # 3. Check if this exact box is already in Home Assistant!
            if not errors:
                await self.async_set_unique_id(box_id_bin)
                self._abort_if_unique_id_configured()

                try:
                    # 4. Live API Verification
                    async with aiohttp.ClientSession() as session:
                        params = {
                            "UserIdBin": user_input["user_id_bin"],
                            "UserSecret": user_input["user_secret"]
                        }
                        async with session.get(API_URL_STATUS, params=params) as resp:
                            if resp.status != 200:
                                raise ValueError("invalid_auth")

                    # 5. Store credentials WITH the custom device name
                    return self.async_create_entry(
                        title=box_name, 
                        data={
                            "box_name": box_name,
                            "box_id_bin": box_id_bin,
                            "user_id_bin": user_input["user_id_bin"],
                            "user_secret": user_input["user_secret"]
                        }
                    )
                except ValueError as e:
                    errors["base"] = str(e)
                except Exception:
                    errors["base"] = "unknown"

        # The UI form presented to the user
        data_schema = vol.Schema({
            vol.Required("box_name", default="My SwitcheOn"): str,
            vol.Required("qr_url", description="Paste the SwitcheOn QR Link here"): str,
            vol.Required("user_id_bin", description="User ID Bin"): str,
            vol.Required("user_secret", description="User Secret"): str,
        })

        return self.async_show_form(
            step_id="user", 
            data_schema=data_schema, 
            errors=errors
        )
