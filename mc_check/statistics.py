import threading

class Statistics:
    def __init__(self):
        self.data = {
            "hits": 0, "bad": 0, "twofa": 0, "sfa": 0, "mfa": 0,
            "xgp": 0, "xgpu": 0, "other": 0, "vm": 0, "errors": 0,
            "retries": 0, "checked": 0, "cpm": 0
        }
        self._lock = threading.Lock()
        self._cpm_lock = threading.Lock()
        self.cpm_buffer = 0

    def increment(self, name: str, value: int = 1):
        with self._lock:
            if name in self.data:
                self.data[name] += value

    def add_cpm(self, value: int = 1):
        with self._cpm_lock:
            self.cpm_buffer += value

    def calculate_cpm(self):
        with self._cpm_lock:
            self.data['cpm'] = self.cpm_buffer * 60
            self.cpm_buffer = 0

    def get_dict(self):
        with self._lock:
            return {
                "Checked": f"{self.data['checked']}",
                "Hits": f"[bold green]{self.data['hits']}[/]",
                "Bad": f"[bold red]{self.data['bad']}[/]",
                "2FA": f"[bold magenta]{self.data['twofa']}[/]",
                "SFA": f"[bold yellow]{self.data['sfa']}[/]",
                "MFA": f"[bold green]{self.data['mfa']}[/]",
                "XGP": f"[cyan]{self.data['xgp']}[/]",
                "XGPU": f"[cyan]{self.data['xgpu']}[/]",
                "Other": f"[dim]{self.data['other']}[/]",
                "Valid Mail": f"[light_magenta]{self.data['vm']}[/]",
                "Retries": f"[dim]{self.data['retries']}[/]",
                "Errors": f"[bold red]{self.data['errors']}[/]",
                "CPM": f"[bold blue]{self.data['cpm']}[/]",
            }
