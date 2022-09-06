from aiohttp_socks import ProxyConnector, ProxyType


async def get_async_connector(proxy):
    protocols = {
        "http": ProxyType.HTTP,
        "https": ProxyType.HTTP,
        "socks4": ProxyType.SOCKS4,
        "socks5": ProxyType.SOCKS5,
    }
    host = proxy[0]
    port = proxy[1]['port']
    protocol = proxy[1]['protocol'].lower()
    proxy_type = protocols[protocol]
    connector = ProxyConnector(
        proxy_type=proxy_type,
        host=host,
        port=port
    )
    return connector
