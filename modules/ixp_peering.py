import time
import re
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.markup import escape
from rich import print

from modules.peeringdb_client import PeeringDBClient
from modules.netbox_client import NetBoxClient
from modules.ip_manager import IPManager
from modules.bgp_manager import BGPManager

# Configuration
MY_ASN = 5405
PEER_GROUP_NAME = "Peering - IXP"

console = Console(emoji=False) # otherwise it overwrites Ipv6 adresses to emojis
pdb_client = PeeringDBClient()

# basic Functions

# generate a list of all mutual IXP locations between 5405 and the target ASN
def get_common_ixps(target_asn):
    with console.status(f"[bold green]Calculating intersection between AS{MY_ASN} and AS{target_asn}...[/bold green]", spinner="dots"):
        target_ixps = pdb_client.get_ixp_presence(target_asn)
        my_ixps = pdb_client.get_ixp_presence(MY_ASN)
        time.sleep(0.5)

    my_ixps_map = {ix['ix_id']: ix for ix in my_ixps}
    common_list = []
    
    for remote_ix in target_ixps:
        ix_id = remote_ix['ix_id']
        if ix_id in my_ixps_map:
            local_ix = my_ixps_map[ix_id]
            common_list.append({
                "ix_name": remote_ix['ix_name'],
                "ix_id": ix_id,
                "local_ip4": local_ix['ipaddr4'],
                "remote_ip4": remote_ix['ipaddr4'],
                "local_ip6": local_ix['ipaddr6'],
                "remote_ip6": remote_ix['ipaddr6'],
            })
    
    return sorted(common_list, key=lambda x: x['ix_name'])

# show summary about the target AS
def display_asn_details(net_info):
    v4_limit = net_info.get('info_prefix_limit_v4') or net_info.get('info_prefixes4')
    v6_limit = net_info.get('info_prefix_limit_v6') or net_info.get('info_prefixes6')

    grid = Table.grid(expand=True)
    grid.add_column(style="bold cyan", width=20)
    grid.add_column()
    
    grid.add_row("Organization:", str(net_info.get('name')))
    grid.add_row("Website:", str(net_info.get('website') or "N/A"))
    grid.add_row("IRR AS-SET:", f"[bold green]{net_info.get('irr_as_set')}[/bold green]")
    
    grid.add_row("IPv4 Max Prefix:", str(v4_limit) if v4_limit else "[dim]Not Set[/dim]")
    grid.add_row("IPv6 Max Prefix:", str(v6_limit) if v6_limit else "[dim]Not Set[/dim]")
    
    console.print(Panel(grid, title=f"AS{net_info.get('asn')} Details", border_style="green"))

# beginning of the wizard
def run_ixp_peering_wizard():
    console.clear()
    console.print(Panel("[bold cyan]WIZARD: Create Peering at IXP[/bold cyan]", border_style="cyan"))
    
    # 1. asking for remote AS, and get details (if possible)
    target_asn_str = Prompt.ask("[bold green]?[/bold green] Enter Peer ASN")
    try:
        target_asn = int(target_asn_str)
    except ValueError:
        console.print("[bold red]❌ ASN must be a number![/bold red]")
        time.sleep(1.5)
        return

    net_info = pdb_client.get_asn_details(target_asn)
    if not net_info:
        console.print(f"[bold red]❌ ASN {target_asn} not found in PeeringDB![/bold red]")
        input("Press Enter...")
        return

    # Show Details with function
    display_asn_details(net_info)

    # 2. get the list of common IXPs with function
    common_ixps = get_common_ixps(target_asn)
    if not common_ixps:
        console.print(f"\n[bold red]⚠️ No common IXPs found between AS{MY_ASN} and AS{target_asn}.[/bold red]")
        input("Press Enter to return...")
        return
    
    # show the list
    console.print(f"\n[bold cyan]=== SELECT IXP SESSION(S) ===[/bold cyan]")
    console.print(f"Found [bold]{len(common_ixps)}[/bold] common exchange points.\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("IXP Name")
    table.add_column("IPv4 Pair", style="green")
    table.add_column("IPv6 Pair", style="green")

    for idx, item in enumerate(common_ixps, 1):
        v4 = f"{item['local_ip4']} -> {item['remote_ip4']}" if item['local_ip4'] and item['remote_ip4'] else "[dim]N/A[/dim]"
        v6 = f"{item['local_ip6']} -> {item['remote_ip6']}" if item['local_ip6'] and item['remote_ip6'] else "[dim]N/A[/dim]"
        table.add_row(str(idx), escape(item['ix_name']), v4, v6)

    console.print(table)
    
    # 3. Selection
    console.print("\n[dim]Enter numbers (e.g. '1,3,5') or 'all'.[/dim]")
    selection_str = Prompt.ask("[bold green]Select IXPs[/bold green]")
    
    selected_indices = []
    if selection_str.lower() == 'all':
        selected_indices = range(1, len(common_ixps) + 1)
    else:
        try:
            parts = [int(s.strip()) for s in selection_str.split(',') if s.strip().isdigit()]
            selected_indices = [val for val in parts if 1 <= val <= len(common_ixps)]
        except ValueError:
            console.print("[bold red]❌ Invalid format![/bold red]")
            return

    if not selected_indices:
        return

    # check for prefix-limit (peeringdb is sometimes funny)
    pdb_limit_v4 = net_info.get('info_prefix_limit_v4') or net_info.get('info_prefixes4') or 0
    pdb_limit_v6 = net_info.get('info_prefix_limit_v6') or net_info.get('info_prefixes6') or 0
    
    final_limit_v4 = int(pdb_limit_v4)
    final_limit_v6 = int(pdb_limit_v6)
    
    # Important! If prefix-limit is invalid, we ask the user for manual input
    if final_limit_v4 == 0:
        console.print(f"[yellow]⚠️  IPv4 Prefix Limit is 0 or missing in PeeringDB.[/yellow]")
        if Prompt.ask("Do you want to set a manual IPv4 limit?", choices=["y", "n"], default="y") == "y":
            while True:
                val = Prompt.ask("Enter IPv4 Limit (integer)")
                if val.isdigit() and int(val) > 0:
                    final_limit_v4 = int(val)
                    break

    if final_limit_v6 == 0:
        console.print(f"[yellow]⚠️  IPv6 Prefix Limit is 0 or missing in PeeringDB.[/yellow]")
        if Prompt.ask("Do you want to set a manual IPv6 limit?", choices=["y", "n"], default="y") == "y":
            while True:
                val = Prompt.ask("Enter IPv6 Limit (integer)")
                if val.isdigit() and int(val) > 0:
                    final_limit_v6 = int(val)
                    break

    # 4. NetBox Validation
    # the goal is to check if the remote IPs exist in IPAM and if the BGP session exists (by any chance) to never duplicate
    console.print(f"\n[bold cyan]=== VALIDATING RESOURCES ===[/bold cyan]")
    
    nb_client = NetBoxClient()
    ip_mgr = IPManager(nb_client)
    bgp_mgr = BGPManager(nb_client)
    
    valid_sessions = []
    status_table = Table(show_header=True, header_style="bold white")
    status_table.add_column("IXP")
    status_table.add_column("Remote IP")
    status_table.add_column("IP Status", style="bold")
    status_table.add_column("BGP Session", style="bold")
    
    for idx in selected_indices:
        ix_data = common_ixps[idx - 1]
        
        ips_to_check = [ip for ip in [ix_data['remote_ip4'], ix_data['remote_ip6']] if ip]
        
        for ip in ips_to_check:
            nb_ip = ip_mgr.get_ip_address(ip)
            bgp_exists = False
            has_subnet = False
            
            if nb_ip:
                ip_status = "[green]✅ Found[/green]"
                has_subnet = True
                if bgp_mgr.get_session_by_ip(ip):
                    bgp_status = f"[green]✅ Found[/green]"
                    bgp_exists = True
                else:
                    bgp_status = "[yellow]⚠️ Missing[/yellow]"
            else:
                bgp_status = "[dim]-[/dim]"
                if ip_mgr.get_prefix_for_ip(ip):
                    ip_status = "[yellow]⚠️ Missing[/yellow]"
                    has_subnet = True
                else:
                    ip_status = "[bold red]❌ No subnet![/bold red]"
                    has_subnet = False
            valid_sessions.append({
                'data': ix_data, 
                'ip_obj': nb_ip, 
                'ip_str': ip, 
                'exists': bool(nb_ip), 
                'bgp_exists': bgp_exists,
                'has_subnet': has_subnet
            })
            
            status_table.add_row(escape(ix_data['ix_name']), ip, ip_status, bgp_status)

    console.print(status_table)

    # build the final session list which can actually be created
    actionable_sessions = [s for s in valid_sessions if not s['bgp_exists'] and s['has_subnet']]
    if not actionable_sessions:
        console.print("\n[bold green]🎉 All sessions already exist! No actions needed.[/bold green]")
        input("Press Enter...")
        return

    # 5. Tenant checking and assignment
    console.print(f"\n[bold cyan]=== TENANT ASSIGNMENT ===[/bold cyan]")
    pdb_name = net_info.get('name')
    console.print(f"Searching NetBox for: [bold]{escape(pdb_name)}[/bold]...")
    
    selected_tenant = None
    search_term = pdb_name

    while not selected_tenant:
        candidates = nb_client.get_tenant_by_name(search_term)
        
        if not candidates:
            console.print(f"[yellow]⚠️ No tenant found for '{escape(search_term)}'.[/yellow]")
            search_term = Prompt.ask("Enter search term (or 'q' to quit)")
            if search_term.lower() == 'q': return
            continue

        if len(candidates) == 1:
            t = candidates[0]
            console.print(f"[green]✅ Match: {escape(t.name)} (ID: {t.id})[/green]")
            if Prompt.ask("Use this Tenant?", choices=["y", "n"], default="y") == "y":
                selected_tenant = t
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
                    selected_tenant = candidates[val - 1]

    console.print(f"[bold green]🔒 Selected: {escape(selected_tenant.name)}[/bold green]")

    # 6. Pre-flight checks and summary
    console.print(f"\n[bold cyan]=== PRE-FLIGHT CHECKS ===[/bold cyan]")
    
    peer_group_id = nb_client.get_peer_group_id(PEER_GROUP_NAME)
    my_asn_obj = nb_client.get_my_asn_object(MY_ASN)
    # check if the tenant has the ASN object in NB
    peer_asn_obj = nb_client.get_asn_for_tenant(target_asn, selected_tenant.id)
    if not peer_asn_obj:
        console.print(f"[bold red]❌ Error: AS{target_asn} not found under tenant '{escape(selected_tenant.name)}'![/bold red]")
        console.print(f"[yellow]Action: Create AS{target_asn} in NetBox assigned to this tenant. Link: https://netbox.as5405.net/ipam/asns/add/[/yellow]")
        input("Press Enter...")
        return
    console.print(f"[green]Remote AS exist in NetBox: {target_asn} (NB ID: {peer_asn_obj.id})[/green]")
    console.print(f"[green]IPv4 Limit: {final_limit_v4} (from PeeringDB)[green]")
    console.print(f"[green]IPv6 Limit: {final_limit_v6} (from PeeringDB)[green]")

    # we don't always need to sync, in case someome's pdb is broken
    should_sync = Prompt.ask("\nEnable 'Sync from PeeringDB'?", choices=["y", "n"], default="y") == "y"
    
    # MD5 password (optional)
    md5_password = Prompt.ask("\nSet MD5 Password? (Leave empty for None)")
    if md5_password.strip():
        console.print(f"[green]🔒 MD5 Password set ({len(md5_password)} chars)[/green]")
    else:
        md5_password = ""

    # 7. Execution

    preview_table = Table(title="Planned BGP Sessions (Dry Run)", show_header=True, header_style="bold magenta")
    preview_table.add_column("IXP Name", style="cyan")
    preview_table.add_column("Remote IP", style="green")
    preview_table.add_column("Limit", justify="right")
    preview_table.add_column("AS-SET", style="yellow")
    preview_table.add_column("MD5", style="red")

    for session in actionable_sessions:
        data = session['data']
        ip_str = session['ip_str']
        
        is_v6 = ':' in ip_str
        limit_val = final_limit_v6 if is_v6 else final_limit_v4
        
        raw_as_set_str = net_info.get('irr_as_set') or ""
        as_set_parts = raw_as_set_str.strip().split(' ')
        preview_as_set = as_set_parts[0] if as_set_parts else "-"
        if as_set_parts and is_v6:
             for candidate in as_set_parts[:2]:
                if "V6" in candidate.upper():
                    preview_as_set = candidate
                    break
        
        md5_status = "Yes" if md5_password else "-"

        preview_table.add_row(
            escape(data['ix_name']), 
            ip_str, 
            str(limit_val), 
            preview_as_set, 
            md5_status
        )

    # draw the table
    console.print(preview_table)

    if Prompt.ask("Do you want to apply these changes to NetBox?", choices=["y", "n"]) == "y":
        console.print("\n[yellow]🚀 Launching Creation...[/yellow]")
        
        for session in actionable_sessions:
            data = session['data']
            ip_str = session['ip_str']
            exists = session['exists']
            
            console.print(f"\n[bold white]--- {escape(data['ix_name'])} ({ip_str}) ---[/bold white]")

            # A) Resolve Local Context & Mask from IPAM
            local_ip_str = data['local_ip4'] if ':' not in ip_str else data['local_ip6']
            console.print(f"   Resolving Local Context from {local_ip_str}...")
            
            local_ip_obj = ip_mgr.get_ip_address(local_ip_str)
            ctx = ip_mgr.get_device_site_from_ip(local_ip_str)

            if not local_ip_obj or not ctx:
                console.print(f"     [bold red]❌ Critical: Local IP {local_ip_str} not found or not assigned to Device![/bold red]")
                continue
            
            try:
                mask = local_ip_obj.address.split('/')[-1]
                target_ip_with_cidr = f"{ip_str}/{mask}"
                console.print(f"     📍 Site: [bold]{ctx['site_name']}[/bold] | Device: [bold]{ctx['device_name']}[/bold]")
            except Exception:
                target_ip_with_cidr = ip_str

            # B) Create Remote IP
            remote_ip_obj = session.get('ip_obj')
            if not exists:
                console.print(f"   Creating Remote IP [cyan]{target_ip_with_cidr}[/cyan]...")
                desc = f"{selected_tenant.name} - {data['ix_name']}"
                new_ip = ip_mgr.create_ip_address(target_ip_with_cidr, selected_tenant.id, desc)
                if new_ip:
                    console.print(f"     [green]✅ IP Created (ID: {new_ip.id})[/green]")
                    session['ip_obj'] = new_ip
                else:
                    console.print(f"     [bold red]❌ IP Creation Failed. Skipping.[/bold red]")
                    continue
            else:
                console.print(f"   [dim]IP exists (ID: {remote_ip_obj.id}).[/dim]")

            # C) Create BGP Session
            is_v6 = ':' in ip_str
            addr_family = "6u" if is_v6 else "4u"
            
            prefix_limit = final_limit_v6 if is_v6 else final_limit_v4
            
            # better AS-SET selection (separate AS-SET from AS-SET-V6)
            raw_as_set_str = net_info.get('irr_as_set') or ""
            as_set_parts = raw_as_set_str.strip().split(' ')
            
            final_as_set = as_set_parts[0] if as_set_parts else ""

            if as_set_parts:
                candidates = as_set_parts[:2] 
                for candidate in candidates:
                    if is_v6 and "V6" in candidate.upper():
                        final_as_set = candidate
                        break

            # cleanup name of non ascii characters
            raw_name = selected_tenant.name
            clean_name = re.sub(r'[^a-zA-Z0-9]', '', raw_name)

            session_name = raw_name
            desc = f"[peer_type=peer_ixp,peer_as={target_asn},peer_name={clean_name}]"
            
            console.print(f"   Creating BGP Session: [bold cyan]{escape(session_name)}[/]...")
            # magic starts here!
            try:
                bgp_s = bgp_mgr.create_bgp_session(
                    name=session_name,
                    site_id=ctx['site_id'],
                    device_id=ctx['device_id'],
                    tenant_id=selected_tenant.id,
                    local_ip_id=local_ip_obj.id,
                    remote_ip_id=session['ip_obj'].id,
                    local_as_id=my_asn_obj.id,
                    remote_as_id=peer_asn_obj.id,
                    peer_group_id=peer_group_id,
                    address_family=addr_family,
                    as_set=final_as_set, 
                    prefix_limit=int(prefix_limit),
                    sync_pdb=should_sync,
                    md5_key=md5_password,
                    description=desc
                )
                console.print(f"     [bold green]✅ BGP Session Created (ID: {bgp_s.id})[/bold green]")
            except Exception as e:
                console.print(f"     [bold red]💥 Creation Failed: {e}[/bold red]")

    else:
        console.print("[dim]Aborted.[/dim]")
    
    input("\nPress Enter to return...")