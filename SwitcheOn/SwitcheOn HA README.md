# **SwitcheOn Custom Integration for Home Assistant**

A custom component for Home Assistant that integrates [SwitcheOn](https://switcheon.com/) remote power switching and temperature monitoring devices.  
This integration connects to the SwitcheOn cloud API to automatically discover your boxes, create switches for your relays (using the custom names you set in the app), and provide sensors for temperature and cellular signal strength.

## **Features**

* 🔌 **Dynamic Switches:** Automatically creates toggles for all available channels (e.g., "Engine Heater", "Neon 1").  
* 🌡️ **Temperature Sensor:** Reads the current box temperature (respects your Celsius/Fahrenheit preference).  
* 📶 **Signal Strength Sensor:** Tracks the cellular connection strength (in dBm).  
* 🔄 **Cloud Polling:** Updates device states every 30 seconds.

## **⚠️ Important Prerequisite: Getting Your Credentials**

SwitcheOn does not use standard usernames and passwords. They use a unique QR code pairing system. To use this integration, **you must intercept the web traffic from the SwitcheOn mobile app** once to extract your account's UserIdBin and UserSecret.

### **How to intercept your credentials:**

1. **Install HTTP Toolkit:** Download and install [HTTP Toolkit](https://httptoolkit.com/) on your PC or Mac.  
2. **Connect an Android Device:** \* **Option A (Emulator):** Use an Android Studio Emulator (Target: "Google APIs").  
   * **Option B (Physical Device):** Plug in your Android phone, enable USB Debugging, and use HTTP Toolkit's "Android device via ADB" to connect. *Note: You may need to use the "Patch App" feature in HTTP Toolkit for the official SwitcheOn app to trust the proxy on a modern physical phone.*  
3. **Capture Traffic:** Open the SwitcheOn app on the connected device and ensure you are logged in / have scanned your box's QR code.  
4. **Find the Credentials:** In HTTP Toolkit, look for a GET request going to:  
   https://www.switcheon.com/api/User?UserIdBin=...  
5. **Save the Data:** From that URL (or the JSON response body), copy your specific:  
   * UserIdBin (e.g., KjqubefLcUiOkYbGMkK9dQ==)  
   * UserSecret (e.g., iuJvxkoNImuKvxpIimkyGBX...)

Keep these safe\! You will need them during the Home Assistant setup.

## **Installation (via HACS)**

The easiest way to install this integration is using the [Home Assistant Community Store (HACS)](https://hacs.xyz/).

1. Open HACS in your Home Assistant dashboard.  
2. Click the three dots ⋮ in the top right corner and select **Custom repositories**.  
3. Paste the URL of this repository.  
4. Select **Integration** as the category and click **Add**.  
5. Close the modal, search for "SwitcheOn" in HACS, and click **Download**.  
6. **Restart Home Assistant.**

## **Configuration**

Once installed and Home Assistant has restarted:

1. Go to **Settings** \> **Devices & Services**.  
2. Click **\+ Add Integration** in the bottom right.  
3. Search for **SwitcheOn**.  
4. You will be prompted to enter three things:  
   * **QR Code Link / Token:** Paste the full HTTPS://SWITCHEON.COM/ACT/... link or just the 32-character hex token from your device's QR code.  
   * **User ID Bin:** The ID you extracted via HTTP Toolkit (ends in \==).  
   * **User Secret:** The Secret string you extracted via HTTP Toolkit.  
5. Click Submit. Your devices will instantly appear\!

## **Troubleshooting**

* **Device already configured:** You can only add a specific SwitcheOn box token once.  
* **Invalid QR Link:** Ensure you are pasting the exact 32-character hexadecimal string found in the QR code (or the full URL containing it).  
* **Switches aren't updating immediately:** This integration relies on cloud polling. When you toggle a switch, it sends the command immediately, but the UI state may take up to 30 seconds to reflect the cloud's confirmed state.