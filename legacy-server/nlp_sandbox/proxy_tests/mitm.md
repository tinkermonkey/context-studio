# Start proxy: mitmdump -s cache_proxy.py -p 8080

```python
# Configure your app to use the proxy
import os
os.environ['HTTP_PROXY'] = 'http://localhost:8080'
os.environ['HTTPS_PROXY'] = 'http://localhost:8080'

# Or set proxy in requests
import requests
proxies = {
    'http': 'http://localhost:8080',
    'https': 'http://localhost:8080'
}

# Monkey patch requests to always use proxy
original_request = requests.request
def proxied_request(*args, **kwargs):
    kwargs.setdefault('proxies', proxies)
    return original_request(*args, **kwargs)

requests.request = proxied_request
```