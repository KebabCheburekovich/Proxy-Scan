from proxy import Proxy

proxy = Proxy(per_request=1000)
p = proxy.get()
proxy.check()
proxy.parse()
