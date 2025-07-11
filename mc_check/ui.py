from rich.panel import Panel

CREDITS = "Author: a11_89d (https://t.me/a11_89d)"
VERSION = "1.0.0"

def create_logo():
    logo_text = """
  __  __  ___  ____ _  __   ____  _  _  ____
 (  )/  \(  _)(  _ ( \/ ) (_  _)( )/ )( ___)
  )(__)(  )_)  ) _ <)  /    )(   )  (  )__)
 (____)(_(___)(____/(__/    (__) (_)\_)(____)
"""
    return Panel(logo_text, style="bold green", title=f"MC-Check v{VERSION}", border_style="green")

def create_credits_panel():
    return Panel(CREDITS, style="bold cyan", title="Credits", border_style="dim")
