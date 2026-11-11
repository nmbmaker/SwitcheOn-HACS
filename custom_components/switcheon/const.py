DOMAIN = "switcheon"
API_BASE_URL = "https://www.switcheon.com/api"
API_URL_STATUS = f"{API_BASE_URL}/User"
API_URL_ACTION = f"{API_BASE_URL}/req"
API_URL_LINK = f"{API_BASE_URL}/BoxUser"

DEFAULT_SCAN_INTERVAL = 60  # Default polling interval in seconds
MIN_SCAN_INTERVAL = 15
MAX_SCAN_INTERVAL = 600
CONF_SCAN_INTERVAL = "scan_interval"
