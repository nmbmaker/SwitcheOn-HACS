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
            
            try:
                # 1. Clean up the user's input
                url = raw_url.upper().strip()
                
                # 2. Extract just the 32-character Hex token
                if "ACT/" in url:
                    hex_token = url.split("ACT/")[1]
                else:
                    hex_token = url # In case they just pasted the token
                
                # 3. Ensure it's exactly 32 characters
                if len(hex_token) != 32:
                    raise ValueError("invalid_qr_link")

                # 4. Convert Hex to Base64
                binary_data = binascii.unhexlify(hex_token)
                box_id_bin = base64.b64encode(binary_data).decode('utf-8')

                # 5. LIVE API VERIFICATION
                async with aiohttp.ClientSession() as session:
                    params = {
                        "UserIdBin": user_input["user_id_bin"],
                        "UserSecret": user_input["user_secret"]
                    }
                    async with session.get(API_URL_STATUS, params=params) as resp:
                        if resp.status != 200:
                            raise ValueError("invalid_auth")

                # 6. Store the credentials securely
                return self.async_create_entry(
                    title="My SwitcheOn Box",
                    data={
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
            vol.Required("qr_url", description="Paste the SwitcheOn QR Link here"): str,
            vol.Required("user_id_bin", description="User ID Bin (from HTTP Toolkit)"): str,
            vol.Required("user_secret", description="User Secret (from HTTP Toolkit)"): str,
        })

        return self.async_show_form(
            step_id="user", 
            data_schema=data_schema, 
            errors=errors
        )
