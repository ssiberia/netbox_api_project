import sys
import os
import time
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt
from rich import print

from modules.ixp_peering import run_ixp_peering_wizard

# Load environment variables
load_dotenv()
console = Console()

def check_env_vars():
    # Checks .env API keys
    required_vars = ["NETBOX_URL", "NETBOX_TOKEN"]
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        console.print(f"[bold red]❌ ERROR: Missing environment variables: {', '.join(missing)}[/bold red]")
        console.print("[yellow]Please populate the .env file with the required keys![/yellow]")
        sys.exit(1)

def print_banner():
    console.clear()
    console.print(Panel.fit(
        "[bold cyan]CHORES TOOLBOX CLI[/bold cyan]\n"
        "[dim]by Attila Kovács[/dim]",
        border_style="cyan"
    ))

def main_menu():
    while True:
        # banner
        print_banner()
        console.print("[bold green]What would you like to do?[/bold green]\n")
        
        console.print("1. [bold green]Create Peering at IXP[/bold green]")
        console.print("2. [dim]Something else (Coming soon...)[/dim]")
        console.print("0. [bold red]Exit[/bold red]")
        print()
        
        choice = IntPrompt.ask("Select an option", choices=["0", "1", "2"])
        
        if choice == 1:
            # call the def from the ixp_peering.py
            run_ixp_peering_wizard()
            
        elif choice == 0:
            console.print("[bold cyan]👋 Goodbye![/bold cyan]")
            sys.exit()
        
        else:
            console.print("[bold red]⚠️ Feature not implemented yet![/bold red]")
            time.sleep(1)

if __name__ == "__main__":
    try:
        check_env_vars()
        main_menu()
    except KeyboardInterrupt:
        console.print("\n[bold red]Aborted by user![/bold red]")
        sys.exit()