import asyncio
import logging
import random
from typing import List
from urllib.parse import urlparse
from browser_viewer import BrowserViewer
from proxy_manager import ProxyManager

logger = logging.getLogger("BrowserManager")

class BrowserManager:
    def __init__(self, channel_url: str, proxy_manager: ProxyManager, max_concurrent: int = 5):
        self.channel_url = channel_url
        self.proxy_manager = proxy_manager
        self.max_concurrent = max_concurrent
        self.viewers: List[BrowserViewer] = []
        self._running = False

    async def start(self):
        self._running = True
        logger.info(f"Starting BrowserManager with {self.max_concurrent} concurrent viewers.")
        tasks = []
        for _ in range(self.max_concurrent):
            tasks.append(asyncio.create_task(self._maintain_viewer()))
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def stop(self):
        self._running = False
        logger.info("Stopping all viewers...")
        stop_tasks = [v.stop() for v in self.viewers]
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)
        self.viewers.clear()

    async def _maintain_viewer(self):
        while self._running:
            proxy_data = self.proxy_manager.get_next_proxy()
            if not proxy_data:
                logger.warning("No proxies available. Waiting 10s...")
                await asyncio.sleep(10)
                continue
            proxy_dict = self._format_proxy(proxy_data)
            viewer = BrowserViewer(self.channel_url, proxy=proxy_dict, headless=True)
            self.viewers.append(viewer)
            try:
                await viewer.start()
            except Exception as e:
                logger.error(f"Viewer crashed: {e}")
            finally:
                if viewer in self.viewers:
                    self.viewers.remove(viewer)
            await asyncio.sleep(random.uniform(3, 8))

    def _format_proxy(self, proxy_data: dict | str) -> dict:
        if isinstance(proxy_data, dict):
            proxy_url = proxy_data.get("url", "")
        else:
            proxy_url = str(proxy_data)
        if "://" not in proxy_url:
            proxy_url = f"http://{proxy_url}"
        parsed = urlparse(proxy_url)
        server = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
        result = {"server": server}
        if parsed.username:
            result["username"] = parsed.username
        if parsed.password:
            result["password"] = parsed.password
        return result
