<div align="center">

  # isuratw

  ![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white) 
  ![FastAPI](https://img.shields.io/badge/FastAPI-Web_UI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
  ![Playwright](https://img.shields.io/badge/Playwright-Automation-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)
  ![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)

</div>

<div align="center">
    <img src="https://i.imgur.com/AXsovMV.png" style="border-radius: 20px;">
</div>
<br />

---

## Features

### **Dashboard & Monitoring**
* **Modern Web UI**: Dark-themed, Discord-inspired interface built with Vanilla JS & CSS.
* **Real-time Stats**: Live tracking of active viewers, total proxies, and uptime.
* **Live Logs**: WebSocket-streamed logs directly in the dashboard.

### **Automation Core**
* **Headless Browsers**: Uses Playwright (Chromium) for realistic viewer simulation.
* **Smart Navigation**: Auto-consents cookies, adjusts quality to 160p (to save bandwidth), and handles playback muting.
* **Resilience**: Auto-restarts viewers if they crash or freeze.

### **Proxy Management**
* **Multi-Protocol**: Supports HTTP, HTTPS, SOCKS4, and SOCKS5.
* **Authentication**: Handles user:pass authentication automatically.
* **Health Check**: Tracks proxy failures and implements cooldowns for bad proxies.
* **Sticky Sessions**: Designed for sticky sessions to ensure stability.

---

## Technical Specifications

### **System Requirements**
* **CPU**: Multi-core processor recommended. Each viewer is a separate process.
* **RAM**: **Crucial Factor**. Each headless instance consumes **~300MB - 500MB**.
  * 5 Viewers ≈ 2.5GB RAM
  * 10 Viewers ≈ 5GB RAM
* **Network**: Stable internet connection. Viewer video is muted and low-quality (160p), but bandwidth usage scales with count.

### **Proxy Recommendations**
* **Residential Proxies**: Highly recommended to avoid detection. Datacenter IPs are often flagged by Twitch.
* **Format**: `protocol://user:pass@host:port` or `host:port:user:pass`.
* **Sticky IPs**: Use sticky sessions (static IP for a duration) rather than rotating per request to maintain viewer stability.

---

## Installation

### Prerequisites
* **Python 3.10** or higher.
* **Google Chrome** installed (Playwright uses its own binary, but good to have).

### Steps

1. **Clone the repository**
    ```bash
    git clone https://github.com/your-username/isuratw.git
    cd isuratw
    ```

2. **Install dependencies**
    ```bash
    pip install -r requirements.txt
    playwright install chromium
    ```

3. **Run the App**
    ```bash
    python launcher.py
    ```

---

## Building .exe

To create a standalone executable file (no Python required):

1. **Install PyInstaller:**
    ```bash
    pip install pyinstaller
    ```

2. **Run the build command:**
    ```bash
    python -m PyInstaller --noconfirm --onefile --windowed --name "isuratw" --icon "static/favicon.ico" --add-data "static;static" launcher.py
    ```

3. **Find your app in the `dist/` folder.**

---

## Disclaimer

> **Educational Purpose Only:** This software is created for educational purposes to explore browser automation and web socket communication. The developer is not responsible for any misuse of this software or penalties applied to accounts. Use at your own risk.

---

<div align="center">
  Made with 💜 by <b>@sudothi</b>
</div>
