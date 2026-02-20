"""
Twitch Viewer Bot - CLI entry point.
"""

import argparse
import asyncio
import signal
import sys
import os

from proxy_manager import ProxyManager
from twitch_viewer import TwitchViewer


def parse_args():
    parser = argparse.ArgumentParser(description="Twitch Viewer Bot")
    parser.add_argument("--channel", "-c", required=True, help="Twitch channel name")
    parser.add_argument("--proxy-file", "-p", default="proxylist.txt", help="Proxy file path")
    parser.add_argument("--max-concurrent", "-m", type=int, default=5, help="Max concurrent connections (Lower for browser mode)")
    parser.add_argument("--mode", choices=["http", "browser"], default="browser", help="Mode: 'http' (Legacy) or 'browser' (Playwright)")
    return parser.parse_args()


async def main_async(args):
    proxy_file = args.proxy_file
    if os.path.exists("valid_proxies.txt"):
        print(" [INFO] Using 'valid_proxies.txt' found from scraper.")
        proxy_file = "valid_proxies.txt"

    proxy_manager = ProxyManager(proxy_file)
    
    if args.mode == "browser":
        from browser_manager import BrowserManager
        print(f" [MODE] Headless Browser (Playwright) - Target: {args.channel}")
        manager = BrowserManager(
            channel_url=f"https://www.twitch.tv/{args.channel}",
            proxy_manager=proxy_manager,
            max_concurrent=args.max_concurrent
        )
        try:
            await manager.start()
        except asyncio.CancelledError:
            await manager.stop()
            
    else:
        # Legacy HTTP Mode
        print(f" [MODE] Legacy HTTP (aiohttp) - Target: {args.channel}")
        viewer = TwitchViewer(
            channel=args.channel,
            proxy_manager=proxy_manager,
            max_concurrent=args.max_concurrent,
        )

        def signal_handler():
            viewer.stop()

        if sys.platform != "win32":
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(signal.SIGINT, signal_handler)

        try:
            await viewer.run()
        except KeyboardInterrupt:
            viewer.stop()


def main():
    args = parse_args()
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
