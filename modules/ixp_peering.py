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
from modules.utils import get_validated_prefix_limits, select_tenant
from modules.base_peering import BasePeeringController
from modules.base_tool import BaseTool
from modules.strategies import StrictAlphanumericStrategy, UnderscoreStrategy

# Configuration
MY_ASN = 5405
PEER_GROUP_NAME = "Peering - IXP"

console = Console(emoji=False) 
pdb_client = PeeringDBClient()


class IxpPeeringController(BasePeeringController):
    """
    Ez a GYEREK (Child).
    Örökli a szerszámokat, és hozzáteszi az IXP-specifikus tudást.
    """

    def fetch_common_ixps(self, target_asn: int):
        self.target_asn = target_asn
        # Figyeld meg: a 'pdb'-t nem paraméterként kapja, hanem előveszi a táskájából (self)!
        target_ixps = self.pdb.get_ixp_presence(target_asn)
        my_ixps = self.pdb.get_ixp_presence(MY_ASN)

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
class IxpPeeringTool(BaseTool):

    @property
    def name(self):
        return "Create Peering at IXP"

    def run(self):
        # Inicializálás
        nb_client = NetBoxClient()
        
        # ITT A LÉNYEG: Létrehozzuk a "Szakembert" (Controller)
        controller = IxpPeeringController(nb_client, pdb_client)

        console.clear()
        console.print(Panel("[bold cyan]WIZARD: Create Peering at IXP[/bold cyan]", border_style="cyan"))
        
        # 1. asking for remote AS
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

        # ITT HÍVJUK MEG A CONTROLLERT (és a View rajzolja a spinnert)
        common_ixps = []
        with console.status(f"[bold green]Calculating intersection...[/bold green]", spinner="dots"):
            # A Controller dolgozik, a View vár
            common_ixps = controller.fetch_common_ixps(target_asn)
            time.sleep(0.5) 

        # Show Details
        display_asn_details(net_info)

        # 2. Check results
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

        # extract and fix prefix-limits
        final_limit_v4, final_limit_v6 = get_validated_prefix_limits(net_info)

        # 4. NetBox Validation
        console.print(f"\n[bold cyan]=== VALIDATING RESOURCES FROM NETBOX===[/bold cyan]")
        
        # A klienst már fent létrehoztuk, nem kell újra
        ip_mgr = IPManager(nb_client)
        bgp_mgr = BGPManager(nb_client)
        
        console.print("[dim]ℹ️  Note: 'Missing IP' is normal; the script will create it for you.\n    However, if the [bold]Subnet[/bold] itself is missing, you must create it manually in NetBox first.[/dim]\n")
        
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

        # build the final session list
        actionable_sessions = [s for s in valid_sessions if not s['bgp_exists'] and s['has_subnet']]
        if not actionable_sessions:
            console.print("\n[bold green]🎉 All sessions already exist! No actions needed.[/bold green]")
            input("Press Enter...")
            return

        # 5. Tenant checking and assignment
        console.print(f"\n[bold cyan]=== TENANT ASSIGNMENT ===[/bold cyan]")
        selected_tenant = select_tenant(nb_client, net_info.get('name'))

        console.print(f"[bold green]🔒 Selected: {escape(selected_tenant.name)}[/bold green]")

        # 6. Pre-flight checks
        console.print(f"\n[bold cyan]=== PRE-FLIGHT CHECKS ===[/bold cyan]")
        
        peer_asn_obj = None
        
        while not peer_asn_obj:
            peer_asn_obj = nb_client.get_asn_for_tenant(target_asn, selected_tenant.id)
            
            if peer_asn_obj:
                console.print(f"[green]✅ Remote AS exists in NetBox: {target_asn} (NB ID: {peer_asn_obj.id})[/green]")
                break 
            
            console.print(f"\n[bold red]❌ Error: AS{target_asn} not found under tenant '{escape(selected_tenant.name)}'![/bold red]")
            console.print(f"[yellow]Action: Create AS{target_asn} in NetBox assigned to this tenant.[/yellow]")
            console.print(f"[dim]Link: https://netbox.as5405.net/ipam/asns/add/[/dim]")
            
            if Prompt.ask("\nHave you created the ASN? (Select 'y' to retry check)", choices=["y", "n"], default="y") == "n":
                console.print("[dim]Aborted by user.[/dim]")
                return
        
        console.print(f"[green]IPv4 Limit: {final_limit_v4} (from PeeringDB)[green]")
        console.print(f"[green]IPv6 Limit: {final_limit_v6} (from PeeringDB)[green]")

        should_sync = Prompt.ask("\nEnable 'Sync from PeeringDB'?", choices=["y", "n"], default="y") == "y"
        
        md5_password = Prompt.ask("\nSet MD5 Password? (Leave empty for None)")
        if md5_password.strip():
            console.print(f"[green]🔒 MD5 Password set ({len(md5_password)} chars)[/green]")
        else:
            md5_password = ""


        # 7. Execution: PREPARE DATA FIRST (Dry Run Logic Optimization)
        my_asn_obj = nb_client.get_my_asn_object(MY_ASN)
        peer_group_id = nb_client.get_peer_group_id(PEER_GROUP_NAME)

        prepared_sessions = []
        
        with console.status("[bold green]Calculating final parameters (Dry Run)...[/bold green]"):
            for session in actionable_sessions:
                data = session['data']
                ip_str = session['ip_str']
                
                # 1. Determine IP Version and Limits
                is_v6 = ':' in ip_str
                addr_family = "6u" if is_v6 else "4u"
                prefix_limit = final_limit_v6 if is_v6 else final_limit_v4
                
                # 2. AS-SET Selection logic
                raw_as_set_str = net_info.get('irr_as_set') or ""
                as_set_parts = raw_as_set_str.strip().split(' ')
                
                final_as_set = as_set_parts[0] if as_set_parts else ""
                if as_set_parts:
                    candidates = as_set_parts[:2] 
                    for candidate in candidates:
                        if is_v6 and "V6" in candidate.upper():
                            final_as_set = candidate
                            break
                
                # 3. Name Sanitization
                raw_name = selected_tenant.name
                strategy = StrictAlphanumericStrategy()
                clean_name = strategy.sanitize(raw_name)
                
                # 4. Description & Session Name Generation
                session_name = raw_name 
                bgp_desc = f"[peer_type=peer_ixp,peer_as={target_asn},peer_name={clean_name}]"
                ip_desc = f"{selected_tenant.name} - {data['ix_name']}"

                # 5. Resolve Local Context & Mask
                local_ip_str = data['local_ip4'] if not is_v6 else data['local_ip6']
                local_ctx = ip_mgr.get_device_site_from_ip(local_ip_str)
                local_ip_obj = ip_mgr.get_ip_address(local_ip_str)
                
                target_ip_with_cidr = ip_str 
                site_name = "[red]???[/red]"
                device_name = "[red]???[/red]"
                ready_to_deploy = False

                if local_ip_obj and local_ctx:
                    try:
                        mask = local_ip_obj.address.split('/')[-1]
                        target_ip_with_cidr = f"{ip_str}/{mask}"
                        site_name = local_ctx['site_name']
                        device_name = local_ctx['device_name']
                        ready_to_deploy = True
                    except Exception:
                        pass
            
                # Store everything in a prepared dict
                prepared_sessions.append({
                    'original_data': session,
                    'is_v6': is_v6,
                    'target_ip_with_cidr': target_ip_with_cidr,
                    'site_name': site_name,
                    'device_name': device_name,
                    'local_ctx': local_ctx,           
                    'local_ip_obj': local_ip_obj,
                    # Store ID context
                    'my_asn_id': my_asn_obj.id,
                    'peer_asn_id': peer_asn_obj.id,
                    'peer_group_id': peer_group_id,
                    'tenant_id': selected_tenant.id,
                    
                    'prefix_limit': int(prefix_limit),
                    'as_set': final_as_set,
                    'addr_family': addr_family,
                    'session_name': session_name,
                    'bgp_desc': bgp_desc,
                    'ip_desc': ip_desc,
                    'ready': ready_to_deploy
                })
        
        deployable_sessions = [p for p in prepared_sessions if p['ready']]

        if not deployable_sessions:
            console.print("[bold red]❌ No sessions are ready to be deployed (check Local IPs in NetBox).[/bold red]")
            input("Press Enter...")
            return

        # --- DISPLAY DRY RUN TABLE ---
        preview_table = Table(title="Planned BGP Sessions (Dry Run)", show_header=True, header_style="bold magenta")
        preview_table.add_column("IXP Name", style="cyan")
        preview_table.add_column("Remote IP / Device", style="green") 
        preview_table.add_column("Limit", justify="right")
        preview_table.add_column("AS-SET", style="yellow")
        preview_table.add_column("MD5", style="red")

        for item in deployable_sessions:
            ix_name = item['original_data']['data']['ix_name']
            md5_status = "Yes" if md5_password else "-"
            
            loc_info = f"{item['target_ip_with_cidr']}\n[dim]on {item['device_name']}[/dim]"
            
            preview_table.add_row(
                escape(ix_name), 
                loc_info, 
                str(item['prefix_limit']), 
                item['as_set'], 
                md5_status
            )

        console.print(preview_table)

        if Prompt.ask(f"Do you want to apply these {len(deployable_sessions)} changes to NetBox?", choices=["y", "n"]) == "y":
            console.print("\n[yellow]🚀 Launching Creation...[/yellow]")
            
            for item in deployable_sessions:
                data = item['original_data']['data']
                session = item['original_data']
                
                console.print(f"\n[bold white]--- {escape(data['ix_name'])} ---[/bold white]")
                console.print(f"     📍 Site: [bold]{item['site_name']}[/bold] | Device: [bold]{item['device_name']}[/bold]")

                # B) Create Remote IP
                remote_ip_obj = session['ip_obj']
                if not session['exists']:
                    console.print(f"   Creating Remote IP [cyan]{item['target_ip_with_cidr']}[/cyan]...")
                    new_ip = ip_mgr.create_ip_address(item['target_ip_with_cidr'], item['tenant_id'], item['ip_desc'])
                    if new_ip:
                        console.print(f"     [green]✅ IP Created (ID: {new_ip.id})[/green]")
                        item['original_data']['ip_obj'] = new_ip 
                    else:
                        console.print(f"     [bold red]❌ IP Creation Failed. Skipping BGP.[/bold red]")
                        continue
                else:
                    console.print(f"   [dim]IP exists (ID: {remote_ip_obj.id}).[/dim]")

                # C) Create BGP Session
                console.print(f"   Creating BGP Session: [bold cyan]{escape(item['session_name'])}[/]...")
                try:
                    bgp_s = bgp_mgr.create_bgp_session(
                        name=item['session_name'],
                        site_id=item['local_ctx']['site_id'],
                        device_id=item['local_ctx']['device_id'],
                        tenant_id=item['tenant_id'],
                        local_ip_id=item['local_ip_obj'].id,
                        remote_ip_id=item['original_data']['ip_obj'].id, 
                        local_as_id=item['my_asn_id'],
                        remote_as_id=item['peer_asn_id'],
                        peer_group_id=item['peer_group_id'],
                        address_family=item['addr_family'],
                        as_set=item['as_set'], 
                        prefix_limit=item['prefix_limit'],
                        sync_pdb=should_sync,
                        md5_key=md5_password,
                        description=item['bgp_desc']
                    )
                    console.print(f"     [bold green]✅ BGP Session Created (ID: {bgp_s.id})[/bold green]")
                except Exception as e:
                    console.print(f"     [bold red]💥 Creation Failed: {e}[/bold red]")

        else:
            console.print("[dim]Aborted.[/dim]")
        
        input("\nPress Enter to return...")