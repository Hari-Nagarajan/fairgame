from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

DEFAULT_TIMEOUT = 5  # seconds


class TimeoutHTTPAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        self.timeout = DEFAULT_TIMEOUT
        super().__init__(
            max_retries=Retry(
                total=10,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                method_whitelist=["HEAD", "GET", "OPTIONS"],
            )
        )

    def send(self, request, **kwargs):
        timeout = kwargs.get("timeout")
        if timeout is None:
            kwargs["timeout"] = self.timeout
        return super().send(request, **kwargs)
