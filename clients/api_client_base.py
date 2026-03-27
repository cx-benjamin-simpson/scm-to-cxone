
import base64
from typing import Any, Callable, Dict, Iterable, Optional
import requests
from misc.logsupport import setup_logger

logger = setup_logger()

class ApiClientBase:
    """
    Shared HTTP client utilities used across providers and Checkmarx:
    - Centralizes requests.Session, verbose logging, Basic PAT header construction, and error handling.
    - Prevents repetition of request, pagination, and header code in provider clients.
    """

    def __init__(self, is_verbose: bool = False):
        self.session = requests.Session()
        self.is_verbose = is_verbose

    @staticmethod
    def build_auth_header(pat: str) -> Dict[str, str]:
        """
        Builds a Basic auth header by base64-encoding ':' + PAT. 
        """
        token = base64.b64encode(f":{pat}".encode("utf-8")).decode("utf-8")
        return {"Authorization": f"Basic {token}"}
    
    def remove_git_extn (self, git_url):  
        url = git_url
        # Find the last index of '.git'
        last_index = git_url.rfind('.git')      
        # If '.git' exists in the url, remove the last occurrence  
        if last_index != -1:  
            url = git_url[:last_index]        
        return url 
    
    def _request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        timeout: int = 60,
    ) -> requests.Response:
        """
        Performs an HTTP request with consistent logging, error propagation, and timeouts. 
        Raises for HTTP errors to let callers handle exceptions at boundaries. 
        """
        # Debugging aid.
        # WARNING: Careful with logging bodies that may contain sensitive info.
        # After all, Checkmarx is in the business of security! :)
        # logger.debug(f"{method.upper()} {url} params={params} body={json_body is not None}")
        resp = self.session.request(
            method=method.upper(),
            url=url,
            headers=headers or {},
            params=params or {},
            json=json_body,
            timeout=timeout,
        )
        if resp.status_code >= 400:
            logger.debug(f"HTTP {resp.status_code} response: {resp.text[:500]}")
        resp.raise_for_status()
        return resp

    def _get_json(self, url: str, headers: Optional[Dict[str, str]] = None, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Convenience for GET returning decoded JSON payloads. 
        """
        return self._request("GET", url, headers=headers, params=params).json()

    def _post_json(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Convenience for POST with JSON body and decoded JSON responses. 
        """
        return self._request("POST", url, headers=headers, params=params, json_body=body).json()

    def paginate(
        self,
        first_url: str,
        headers: Dict[str, str],
        params: Dict[str, Any],
        next_link_fn: Callable[[requests.Response], Optional[str]],
    ) -> Iterable[Any]:
        """
        Generic pagination iterator:
        - Yields JSON pages while following a 'next' link resolved by next_link_fn(response). 
        """
        url = first_url
        while url:
            resp = self._request("GET", url, headers=headers, params=params)
            yield resp.json()
            url = next_link_fn(resp)
