from rich.prompt import Prompt
from rich.console import Console
from rich.markup import escape

console = Console()

def get_validated_prefix_limits(net_info):
    """
    exctracts prefix-limits from the PeeringDB data
    If the limit is missing, or 0, it'll interactively ask the user to enter a limit.
    
    Returns:
        tuple: (limit_v4, limit_v6) integers
    """
    # 1. extract raw data
    raw_v4 = net_info.get('info_prefix_limit_v4') or net_info.get('info_prefixes4') or 0
    raw_v6 = net_info.get('info_prefix_limit_v6') or net_info.get('info_prefixes6') or 0
    
    final_limit_v4 = int(raw_v4)
    final_limit_v6 = int(raw_v6)

    # 2. ask manually, if IPv4 limit is 0
    if final_limit_v4 == 0:
        console.print(f"[yellow]⚠️  IPv4 Prefix Limit is 0 or missing in PeeringDB.[/yellow]")
        if Prompt.ask("Do you want to set a manual IPv4 limit?", choices=["y", "n"], default="y") == "y":
            while True:
                val = Prompt.ask("Enter IPv4 Limit (integer)")
                if val.isdigit() and int(val) > 0:
                    final_limit_v4 = int(val)
                    break

    # 3. ask manually, if IPv6 limit is 0
    if final_limit_v6 == 0:
        console.print(f"[yellow]⚠️  IPv6 Prefix Limit is 0 or missing in PeeringDB.[/yellow]")
        if Prompt.ask("Do you want to set a manual IPv6 limit?", choices=["y", "n"], default="y") == "y":
            while True:
                val = Prompt.ask("Enter IPv6 Limit (integer)")
                if val.isdigit() and int(val) > 0:
                    final_limit_v6 = int(val)
                    break
                    
    return final_limit_v4, final_limit_v6

def select_tenant(nb_client, initial_search_term):
    """
    Interactive Tenant chooser.
    
    Args:
        nb_client: The NetBoxClient entity.
        initial_search_term (str): name to search for (eg. a PeeringDB name).
        
    Returns:
        object: the choosen tenant object, or None, if the user quit.
    """
    console.print(f"Searching NetBox for: [bold]{escape(initial_search_term)}[/bold]...")
    search_term = initial_search_term
    
    while True:
        candidates = nb_client.get_tenant_by_name(search_term)
        
        if not candidates:
            console.print(f"[yellow]⚠️ No tenant found for '{escape(search_term)}'.[/yellow]")
            search_term = Prompt.ask("Enter search term (or 'q' to quit)")
            if search_term.lower() == 'q':
                return None
            continue

        if len(candidates) == 1:
            t = candidates[0]
            console.print(f"[green]✅ Match: {escape(t.name)} (ID: {t.id})[/green]")
            if Prompt.ask("Use this Tenant?", choices=["y", "n"], default="y") == "y":
                return t
            else:
                search_term = Prompt.ask("Enter search term")
        else:
            console.print(f"[cyan]Multiple tenants found:[/cyan]")
            for i, t in enumerate(candidates, 1):
                print(f"{i}. {escape(t.name)} ({escape(t.slug)})")
            
            sel = Prompt.ask("Select # (or 0 to search again)")
            if sel.isdigit():
                val = int(sel)
                if val == 0: 
                    search_term = Prompt.ask("Enter search term")
                elif 1 <= val <= len(candidates): 
                    return candidates[val - 1]