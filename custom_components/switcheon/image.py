import base64
import io
import segno

from homeassistant.components.image import ImageEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util, slugify
from .const import DOMAIN
from .sensor import build_device_info, get_device_name


def _build_qr_payload(entry, box_data: dict) -> str:
    """Return the exact scanned QR URL, or reconstruct from boxIdText / box_id_bin."""
    saved_qr = (entry.data.get("qr_url") or "").strip()
    if saved_qr:
        if len(saved_qr) == 32 and all(c in "0123456789abcdefABCDEF" for c in saved_qr):
            return f"https://www.switcheon.com/act/{saved_qr.upper()}"
        return saved_qr

    hex_token = (box_data.get("boxIdText") or "").strip().upper()
    if not hex_token and entry.data.get("box_id_bin"):
        raw_bytes = base64.b64decode(entry.data["box_id_bin"])
        hex_token = raw_bytes.hex().upper()

    return f"https://www.switcheon.com/act/{hex_token}"


def _render_qr_png(payload: str) -> bytes:
    """Render a crisp high-contrast QR PNG via segno."""
    qr = segno.make_qr(payload, error="m")
    buffer = io.BytesIO()
    qr.save(buffer, kind="png", scale=10, border=4, dark="#000000", light="#FFFFFF")
    return buffer.getvalue()


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the SwitcheOn QR Code image entity."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SwitcheOnQrImage(hass, coordinator, entry)])


class SwitcheOnQrImage(CoordinatorEntity, ImageEntity):
    """Diagnostic ImageEntity displaying the scannable SwitcheOn box QR code."""

    _attr_has_entity_name = False
    _attr_content_type = "image/png"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:qrcode"

    def __init__(self, hass, coordinator, entry):
        """Initialize the QR code image entity."""
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)

        self.entry = entry
        self.box_id_bin = entry.data["box_id_bin"]
        unique_prefix = entry.unique_id or self.box_id_bin
        device_name = get_device_name(entry)
        device_slug = slugify(device_name)

        box_data = coordinator.data if isinstance(coordinator.data, dict) else {}
        self._attr_device_info = build_device_info(entry, box_data)

        self._qr_payload = _build_qr_payload(entry, box_data)
        self._cached_png: bytes | None = None
        self._attr_image_last_updated = dt_util.utcnow()

        self._attr_name = f"{device_name} QR Code"
        self._attr_unique_id = f"{unique_prefix}_qr_code"
        self.entity_id = f"image.switcheon_{device_slug}_qr_code"

    @property
    def extra_state_attributes(self):
        """Expose the activation URL text alongside the QR image."""
        return {"activation_url": self._qr_payload}

    async def async_image(self) -> bytes | None:
        """Generate PNG bytes once and serve from cache."""
        if self._cached_png is None:
            self._cached_png = await self.hass.async_add_executor_job(
                _render_qr_png, self._qr_payload
            )
        return self._cached_png
