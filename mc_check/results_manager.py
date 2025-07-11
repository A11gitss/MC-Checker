import threading
from pathlib import Path
from rich.console import Console

console = Console()

RESULTS_DIR = Path.cwd() / "results"

class ResultsManager:
    def __init__(self, base_filename: str):
        self.results_path = RESULTS_DIR / base_filename
        self.results_path.mkdir(parents=True, exist_ok=True)
        self._locks = {}

    def _get_lock(self, filename: str) -> threading.Lock:
        if filename not in self._locks:
            self._locks[filename] = threading.Lock()
        return self._locks[filename]

    def save(self, category: str, content: str):
        lock = self._get_lock(category)
        with lock:
            try:
                with open(self.results_path / f"{category}.txt", "a", encoding="utf-8") as f:
                    f.write(content + "\n")
            except Exception as e:
                console.log(f"[bold red]Error saving to {category}.txt: {e}[/bold red]")
