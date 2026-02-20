import asyncio
import random
import logging
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("BrowserViewer")

class BrowserViewer:
    def __init__(self, channel_url: str, proxy: Optional[dict] = None, headless: bool = True):
        self.channel_url = channel_url
        self.proxy = proxy
        self.headless = headless
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._running = False

    async def start(self):
        self._running = True
        try:
            await self._launch_browser()
            await self._setup_page()
            await self._navigate_and_watch()
        except Exception as e:
            proxy_name = self.proxy['server'] if self.proxy else 'DIRECT'
            logger.error(f"Erro no viewer ({proxy_name}): {e}")
        finally:
            await self.stop()

    async def stop(self):
        self._running = False
        try:
            if self.context:
                await self.context.close()
        except: pass
        try:
            if self.browser:
                await self.browser.close()
        except: pass
        try:
            if self.playwright:
                await self.playwright.stop()
        except: pass
        logger.info("Viewer encerrado.")

    async def _launch_browser(self):
        self.playwright = await async_playwright().start()
        args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-first-run",
            "--no-service-autorun",
            "--password-store=basic",
            "--mute-audio",
            "--autoplay-policy=no-user-gesture-required",
        ]
        proxy_config = None
        if self.proxy:
            proxy_config = {"server": self.proxy["server"]}
            if self.proxy.get("username"):
                proxy_config["username"] = self.proxy["username"]
            if self.proxy.get("password"):
                proxy_config["password"] = self.proxy["password"]
        launch_kwargs = {
            "headless": self.headless,
            "args": args,
        }
        if proxy_config:
            launch_kwargs["proxy"] = proxy_config
        self.browser = await self.playwright.chromium.launch(**launch_kwargs)
        self.context = await self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
            locale="en-US",
            timezone_id="America/New_York",
            java_script_enabled=True,
        )
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)

    async def _setup_page(self):
        self.page = await self.context.new_page()

    async def _navigate_and_watch(self):
        proxy_name = self.proxy['server'] if self.proxy else 'DIRECT'
        logger.info(f"Navigating to {self.channel_url} via {proxy_name}")
        self.page.set_default_timeout(60000)
        await self.page.goto(self.channel_url, wait_until="domcontentloaded", timeout=30000)
        logger.info(f"Page loaded ({proxy_name})")
        await asyncio.sleep(8)
        await self._handle_consent_only()
        try:
            await self.page.wait_for_selector("video", timeout=30000)
            logger.info(f"Video element found ({proxy_name})")
        except:
            logger.warning(f"Video NOT found ({proxy_name})")
            return
        await asyncio.sleep(10)
        is_playing = await self._verify_playback()
        if is_playing:
            logger.info(f"=== STREAM PLAYING! ({proxy_name}) ===")
        else:
            await self._force_playback()
            await asyncio.sleep(5)
            is_playing = await self._verify_playback()
            if is_playing:
                logger.info(f"=== STREAM PLAYING after JS play! ({proxy_name}) ===")
            else:
                logger.warning(f"Video not playing ({proxy_name})")
        await self._set_lowest_quality()
        watch_count = 0
        while self._running:
            if self.page.is_closed():
                break
            watch_count += 1
            if watch_count % 6 == 0:
                still_playing = await self._verify_playback()
                if not still_playing:
                    logger.warning(f"Playback stopped, forcing ({proxy_name})")
                    await self._force_playback()
            await asyncio.sleep(30)
            logger.info(f"Watching #{watch_count} ({proxy_name})")

    async def _handle_consent_only(self):
        for selector in [
            '.consent-banner button',
            '[data-a-target="consent-banner-accept"]',
            'button:has-text("Accept")',
        ]:
            try:
                btn = self.page.locator(selector)
                if await btn.count() > 0 and await btn.first.is_visible():
                    await btn.first.click()
                    logger.info(f"Clicked consent: {selector}")
                    await asyncio.sleep(1)
            except:
                pass

    async def _set_lowest_quality(self):
        try:
            gear = self.page.locator('[data-a-target="player-settings-button"]')
            if await gear.count() > 0:
                await gear.first.click()
                await asyncio.sleep(0.5)
                quality = self.page.locator('[data-a-target="player-settings-menu-item-quality"]')
                if await quality.count() > 0:
                    await quality.first.click()
                    await asyncio.sleep(0.5)
                    options = self.page.locator('[data-a-target="player-settings-submenu-quality-option"]')
                    count = await options.count()
                    if count > 0:
                        await options.nth(count - 1).click()
                        logger.info(f"Set quality to lowest (option {count})")
                    else:
                        await gear.first.click()
                else:
                    await gear.first.click()
        except Exception as e:
            logger.debug(f"Quality setting failed: {e}")

    async def _force_playback(self):
        try:
            await self.page.evaluate("""
                () => {
                    const video = document.querySelector('video');
                    if (video) {
                        video.muted = true;
                        video.play().catch(() => {});
                    }
                }
            """)
        except:
            pass

    async def _verify_playback(self) -> bool:
        try:
            result = await self.page.evaluate("""
                () => {
                    const v = document.querySelector('video');
                    if (!v) return { playing: false };
                    return {
                        playing: !v.paused && v.readyState >= 2 && v.currentTime > 0,
                        paused: v.paused,
                        readyState: v.readyState,
                        currentTime: v.currentTime,
                    };
                }
            """)
            return result.get('playing', False)
        except:
            return False
