import base64
import binascii
import logging
import re
import secrets
import string
import uuid
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    FileSelector,
    FileSelectorConfig,
    TextSelector,
)
from .const import API_URL_LINK, API_URL_STATUS, DOMAIN

_LOGGER = logging.getLogger(__name__)

ALPHANUM = string.ascii_letters + string.digits


def _generate_credentials() -> tuple[str, str]:
    """Generate a 16-byte Base64 GUID (userIdBin) and 32-char alphanumeric secret."""
    user_id_bin = base64.b64encode(uuid.uuid4().bytes).decode("utf-8")
    user_secret = "".join(secrets.choice(ALPHANUM) for _ in range(32))
    return user_id_bin, user_secret


def _decode_qr_upload(hass, uploaded_file_id: str) -> str:
    """Process uploaded QR screenshot/photo and extract barcode text in executor."""
    from pyrxing import read_barcodes

    with process_uploaded_file(hass, uploaded_file_id) as file_path:
        results = read_barcodes(str(file_path))
        for barcode in results or []:
            text = getattr(barcode, "text", "") or ""
            if re.search(r"([0-9a-fA-F]{32})", text):
                return text
        if results:
            return getattr(results[0], "text", "") or ""
    raise ValueError("qr_not_detected")


class SwitcheOnConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Zero-credential QR setup flow for SwitcheOn."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Prompt solely for Device Name and QR Screenshot (or optional URL)."""
        errors = {}

        if user_input is not None:
            box_name = (user_input.get("box_name") or "").strip() or "SwitcheOn"
            qr_image_id = user_input.get("qr_image")
            raw_url = (user_input.get("qr_url") or "").strip()

            qr_source_text = raw_url

            if not qr_image_id and not qr_source_text:
                errors["base"] = "missing_qr"
            elif qr_image_id and not qr_source_text:
                try:
                    qr_source_text = await self.hass.async_add_executor_job(
                        _decode_qr_upload, self.hass, qr_image_id
                    )
                except ValueError as err:
                    errors["qr_image"] = str(err)
                except Exception as err:
                    _LOGGER.exception("Failed decoding QR image: %s", err)
                    errors["qr_image"] = "qr_not_detected"

            box_id_bin = None
            if not errors:
                match = re.search(r"([0-9a-fA-F]{32})", qr_source_text)
                if not match:
                    errors["base"] = "invalid_qr_link"
                else:
                    hex_token = match.group(1).upper()
                    box_id_bin = base64.b64encode(
                        binascii.unhexlify(hex_token)
                    ).decode("utf-8")

            if not errors and box_id_bin:
                await self.async_set_unique_id(box_id_bin)
                self._abort_if_unique_id_configured()

                try:
                    user_id_bin, user_secret = await self._get_or_register_user()
                    await self._link_box(user_id_bin, user_secret, box_id_bin)

                    boxes = await self._fetch_boxes(user_id_bin, user_secret)
                    if not any(b.get("boxIdBin") == box_id_bin for b in boxes):
                        raise ValueError("box_not_found")

                    return self.async_create_entry(
                        title=box_name,
                        data={
                            "box_name": box_name,
                            "box_id_bin": box_id_bin,
                            "qr_url": qr_source_text.strip(),
                            "user_id_bin": user_id_bin,
                            "user_secret": user_secret,
                        },
                    )
                except ValueError as err:
                    errors["base"] = str(err)
                except Exception as err:
                    _LOGGER.exception("SwitcheOn setup error: %s", err)
                    errors["base"] = "cannot_connect"

        data_schema = vol.Schema(
            {
                vol.Required("box_name"): TextSelector(),
                vol.Optional("qr_image"): FileSelector(
                    FileSelectorConfig(accept="image/*")
                ),
                vol.Optional("qr_url"): TextSelector(),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def _get_or_register_user(self) -> tuple[str, str]:
        """Reuse saved HA user credentials if available, else push a new user via PUT /api/User."""
        for existing in self._async_current_entries():
            uid = existing.data.get("user_id_bin")
            sec = existing.data.get("user_secret")
            if uid and sec:
                return uid.strip(), sec.strip()

        user_id_bin, user_secret = _generate_credentials()
        session = async_get_clientsession(self.hass)
        payload = {
            "userIdBin": user_id_bin,
            "userSecret": user_secret,
            "firstname": "Home",
            "lastname": "Assistant",
            "email": "",
            "version": "1.34",
            "platform": "Android",
        }
        async with session.put(API_URL_STATUS, json=payload) as resp:
            if not (200 <= resp.status < 300):
                body = await resp.text()
                _LOGGER.error(
                    "SwitcheOn user registration failed (%s): %s", resp.status, body
                )
                raise ValueError("cannot_register")

        return user_id_bin, user_secret

    async def _link_box(
        self, user_id_bin: str, user_secret: str, box_id_bin: str
    ) -> None:
        """Authorize this user on the scanned box via PUT /api/BoxUser."""
        session = async_get_clientsession(self.hass)
        payload = {
            "userIdBin": user_id_bin,
            "userSecret": user_secret,
            "boxIdBin": box_id_bin,
        }
        async with session.put(API_URL_LINK, json=payload) as resp:
            if not (200 <= resp.status < 300):
                body = await resp.text()
                _LOGGER.error(
                    "SwitcheOn box link failed (%s): %s", resp.status, body
                )
                raise ValueError("box_not_found")

    async def _fetch_boxes(self, user_id_bin: str, user_secret: str) -> list:
        """Verify credentials and return linked boxes from GET /api/User."""
        session = async_get_clientsession(self.hass)
        params = {"UserIdBin": user_id_bin, "UserSecret": user_secret}
        async with session.get(API_URL_STATUS, params=params) as resp:
            if resp.status != 200:
                raise ValueError("invalid_auth")
            data = await resp.json()
            return data.get("boxes") or []
