import uvicorn
import webbrowser
import threading
import time
import sys
import os

if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

def start_server():
    uvicorn.run("web_server:app", host="127.0.0.1", port=8080, log_level="error", reload=False)

if __name__ == "__main__":
    print("--------------------------------------------------")
    print("   isuratw - Twitch Viewer Bot")
    print("   Starting server...")
    print("--------------------------------------------------")

    t = threading.Thread(target=start_server, daemon=True)
    t.start()

    time.sleep(3)

    print("Opening browser at http://127.0.0.1:8080")
    try:
        webbrowser.open("http://127.0.0.1:8080")
    except:
        print("Could not open browser automatically. Please open http://127.0.0.1:8080 manually.")

    print("\n[INFO] Keep this window open while using the bot.")
    print("[INFO] Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        sys.exit(0)
