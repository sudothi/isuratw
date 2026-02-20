import time

class ProxyManager:
    COOLDOWN_SECONDS = 60
    def __init__(self, proxy_file: str, protocol: str = "ipv6"):
        self.proxy_file = proxy_file
        self.protocol = protocol.lower()
        self._proxies: list[dict] = []
        self._cooldowns: dict[str, float] = {}
        self._fail_counts: dict[str, int] = {}
        self._load_proxies()

    def _normalize_proxy(self, raw: str) -> dict | None:
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            return None
        if "://" in raw:
            scheme = raw.split("://", 1)[0].lower()
            if scheme in ("socks5", "socks4"):
                return {"url": raw, "type": "socks"}
            return {"url": raw, "type": "http"}
        if raw.startswith("["):
            bracket_end = raw.find("]")
            if bracket_end == -1:
                return None
            ipv6_host = raw[: bracket_end + 1]
            rest = raw[bracket_end + 1 :]
            parts = rest.lstrip(":").split(":")
            if len(parts) >= 3:
                port, user, passwd = parts[0], parts[1], parts[2]
                url = f"http://{user}:{passwd}@{ipv6_host}:{port}"
            elif len(parts) >= 1 and parts[0]:
                url = f"http://{ipv6_host}:{parts[0]}"
            else:
                url = f"http://{ipv6_host}:443"
            return {"url": url, "type": "http"}
        parts = raw.split(":")
        if len(parts) == 4:
            ip, port, user, passwd = parts
            url = f"http://{user}:{passwd}@{ip}:{port}"
        elif len(parts) == 2:
            url = f"http://{parts[0]}:{parts[1]}"
        elif len(parts) == 1:
            url = f"http://{parts[0]}:443"
        else:
            url = f"http://[{raw}]:443"
        return {"url": url, "type": "http"}

    def _load_proxies(self):
        try:
            with open(self.proxy_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            raise Exception(f"Arquivo não encontrado: {self.proxy_file}")
        for line in lines:
            proxy = self._normalize_proxy(line)
            if proxy:
                self._proxies.append(proxy)
        if not self._proxies:
            raise Exception("Nenhum proxy válido encontrado no arquivo!")

    def get_all_active(self) -> list[dict]:
        now = time.time()
        active = []
        for proxy in self._proxies:
            url = proxy["url"]
            if url in self._cooldowns:
                if now >= self._cooldowns[url]:
                    del self._cooldowns[url]
                    self._fail_counts.pop(url, None)
                    active.append(proxy)
            else:
                active.append(proxy)
        return active

    def report_failure(self, proxy_url: str):
        self._fail_counts[proxy_url] = self._fail_counts.get(proxy_url, 0) + 1
        if self._fail_counts[proxy_url] >= 3:
            cooldown_time = self.COOLDOWN_SECONDS * min(self._fail_counts[proxy_url] // 3, 5)
            self._cooldowns[proxy_url] = time.time() + cooldown_time

    def report_success(self, proxy_url: str):
        self._fail_counts.pop(proxy_url, None)

    @property
    def total_count(self) -> int:
        return len(self._proxies)

    @property
    def active_count(self) -> int:
        return len(self.get_all_active())

    @property
    def cooldown_count(self) -> int:
        return self.total_count - self.active_count

    def get_next_proxy(self) -> dict | None:
        active = self.get_all_active()
        if not active:
            return None
        import random
        return random.choice(active)
