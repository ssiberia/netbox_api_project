import sys
import os
import time
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt
from rich import print

# Importáljuk az eszközeinket (Most még csak egy van)
from modules.ixp_peering import IxpPeeringTool
# Később ide jöhet majd: from modules.pni_peering import PniPeeringTool

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
        "[dim]by Attila Kovacs[/dim]",
        border_style="cyan"
    ))

def main_menu():
    # --- A LISTA (Command Pattern) ---
    # Itt regisztráljuk a rendszerbe az elérhető "Munkásokat".
    # Ha új modult írsz, csak add hozzá ehhez a listához, és kész!
    tools = [
        IxpPeeringTool(),
        # PniPeeringTool(), 
        # SiteProvisioningTool(),
    ]

    while True:
        print_banner()
        console.print("[bold green]What would you like to do?[/bold green]\n")
        
        # --- DINAMIKUS MENÜ GENERÁLÁS ---
        # A main.py nem tudja, mik ezek, csak megkérdezi a nevüket (.name)
        for idx, tool in enumerate(tools, 1):
            console.print(f"{idx}. [bold green]{tool.name}[/bold green]")
        
        console.print("0. [bold red]Exit[/bold red]")
        print()
        
        # Választás
        valid_choices = [str(i) for i in range(len(tools) + 1)]
        choice = IntPrompt.ask("Select an option", choices=valid_choices)
        
        if choice == 0:
            console.print("[bold cyan]👋 Goodbye![/bold cyan]")
            sys.exit()
        
        # --- FUTTATÁS ---
        # A kiválasztott eszköz (.run) metódusát hívjuk meg.
        # Ez a polimorfizmus: minden eszköz mást csinál a .run()-ra, de a main.py-t ez nem érdekli.
        selected_tool = tools[choice - 1]
        
        try:
            selected_tool.run()
        except Exception as e:
            console.print(f"\n[bold red]💥 Error running '{selected_tool.name}': {e}[/bold red]")
            input("Press Enter to continue...")

if __name__ == "__main__":
    try:
        check_env_vars()
        main_menu()
    except KeyboardInterrupt:
        console.print("\n[bold red]Aborted by user![/bold red]")
        sys.exit()
    except Exception as e: 
        console.print(f"\n[bold red]💥 CRITICAL ERROR: {e}[/bold red]")
        sys.exit(1)