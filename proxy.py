import asyncio
import os
import re

import aiohttp
from urllib.parse import urlparse
from configparser import ConfigParser
from helpers import get_async_connector
from typing import List, Dict, Optional, Union
import time

from tqdm import tqdm


def runtime(func):
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        end = time.time()
        if len(result):
            print(f"[*] Execution time: {end - start} seconds.")
            # print(f"[*] Average execution time: {(end - start) / len(result)} seconds.")
        else:
            print(f"[*] No one proxy is responding.")
        return result

    return wrapper


class Proxy:
    _proxies = {}
    _proxy_header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.62 Safari/537.36",
    }
    _timeout = 5
    _url = "https://www.google.ru/"
    _average_time = 0
    _proxy_sources = None
    _protocols = ["HTTP", "SOCKS4", "SOCKS5"]

    def __init__(self, per_request=50):
        self._status_codes = [200]
        self._sem = per_request
        regex = (
            r"(\d+.\d+.\d+.\d+):(\d+)"
        )
        self._regex = re.compile(regex)

    def _read_config(self):
        cfg = ConfigParser(interpolation=None)
        cfg.read(rf"{os.path.dirname(__file__)}\config.ini",
                 encoding="utf-8")
        http = cfg["HTTP"].get("Sources")
        socks4 = cfg["SOCKS4"].get("Sources")
        socks5 = cfg["SOCKS5"].get("Sources")
        self._proxy_sources = {
            proto: tuple(filter(None, sources.splitlines()))
            for proto, sources in (
                ("http", http),
                ("socks4", socks4),
                ("socks5", socks5),
            )

        }

    @staticmethod
    def _convert_proxies(proxy):
        return [f"{x[1]['protocol'].lower()}://{x[0]}:{x[1]['port']}" for x in proxy.items()]

    async def _add_proxy(self, ip: str, port: Union[str, int], protocol: str):
        host = {ip: {
            "port": port,
            "protocol": protocol
        }}
        self._proxies.update(host)

    async def _parse_proxies(self, url, protocol, session, **kwargs):
        self._proxy_header["origin"] = urlparse(url).hostname
        try:
            async with session.get(url, headers=self._proxy_header, **kwargs) as response:
                if response.status != 200:
                    raise
                proxies = tuple(self._regex.findall(await response.text()))
                if proxies:
                    for proxy in proxies:
                        await self._add_proxy(proxy[0], proxy[1], protocol)
            print(f"Success - {url}")
        except Exception as e:
            print(f"Error - {url}")

    def get(self, proxy_sources: Dict = None, timeout: float = None):
        timeout = timeout or self._timeout
        if proxy_sources is None:
            self._read_config()
        else:
            if not set(proxy_sources.keys()).issubset(self._protocols):
                raise KeyError("Supports only http, socks4/5 protocols")

            self._proxy_sources = proxy_sources

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._get_proxies(timeout=timeout))

        return self._proxies

    async def _get_proxies(self, **kwargs):
        self._proxies = {}
        tasks = []
        async with aiohttp.ClientSession() as session:
            for protocol, urls in self._proxy_sources.items():
                for url in urls:
                    tasks.append(self._parse_proxies(url, protocol, session, **kwargs))

            await asyncio.gather(*tasks)

    @runtime
    async def _proxies_tasks(self, method, url, status_codes, **kwargs):
        tasks = []
        sema = asyncio.BoundedSemaphore(self._sem)
        for proxy in self._proxies.items():
            # proxy = self.parse_proxy_data(host)
            task = self._check_proxies(method, url, sema, proxy, status_codes, **kwargs)
            tasks.append(task)
        result = [await f for f in tqdm(asyncio.as_completed(tasks), total=len(tasks))]
        # result = await asyncio.gather(*tasks)
        # result = [x for x in result if x]
        valid_poxy = {}
        for task in result:
            valid_poxy.update(task)
        return valid_poxy

    async def _check_proxies(self, method, url, sema, proxy, status_codes, **kwargs):
        try:
            connector = await get_async_connector(proxy)
            async with aiohttp.ClientSession(connector=connector) as session:
                # async with sema, session.get(url, headers=self._proxy_header,
                #                              timeout=self._timeout) as response:
                async with sema:
                    start_time = time.time()
                    async with session.request(method, url, headers=self._proxy_header, **kwargs) as response:
                        if response.status in status_codes:
                            self._average_time += time.time() - start_time
                            return {proxy[0]: {
                                "port": proxy[1]['port'],
                                "protocol": proxy[1]['protocol']
                            }}
        except Exception:
            pass
        return {}

    def check(self, method: str = "get", url: str = None, proxies: Dict = None, status_codes: List = None,
              timeout: float = None) -> Optional[
        Dict]:
        """
        :param url: for example: "https://www.google.ru/"
        :param method: default "get", can be different
        :param proxies: pass
        :param status_codes: status codes of responses which are considered valid
        :param timeout: request timeout
        :return:
        """
        timeout = timeout or self._timeout
        if status_codes is None:
            status_codes = [200]
        status_codes = status_codes or self._status_codes
        self._proxies = proxies or self._proxies
        url = url or self._url

        loop = asyncio.get_event_loop()
        self._proxies = loop.run_until_complete(self._proxies_tasks(method, url, status_codes, timeout=timeout))

        if len(self._proxies):
            print(f"[*] Average execution time: {self._average_time / len(self._proxies)} seconds.")
        print(f"[*] Valid proxies: {len(self._proxies)}")
        # reqs = []
        # for _, host in enumerate(proxy):
        #     host = self.get_proxy_settings(host)
        #     proxies = {"http": host, "https": host}
        #     reqs.append(grequests.get(url, headers=self._proxy_header, proxies=proxies))
        # for resp in grequests.imap(reqs, size=50, exception_handler=exception_handler):
        #     print(resp)
        # task = asyncio.ensure_future(self._check_proxy(sem, url, session, proxy))
        #     tasks.append(task)
        # responses = await asyncio.gather(*tasks)
        return self._proxies

    def parse(self, proxies: Dict = None) -> List:
        """

        :param proxies: proxies: {"127.0.0.1": {"port": 7777, "protocol": "HTTP"}}
        :return: proxies list
        """
        proxies = proxies or self._proxies
        proxies = self._convert_proxies(proxies)
        return proxies
