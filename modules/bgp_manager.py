from typing import Optional

class BGPManager:
    """Dedicated manager for BGP Session operations in NetBox."""
    def __init__(self, nb_client):
        self.nb = nb_client.nb

    def get_session_by_ip(self, ip_address: str) -> Optional[object]:
        """Checks if a BGP session exists involving this IP address."""
        try:
            ip_obj = self.nb.ipam.ip_addresses.get(address=ip_address)
            if not ip_obj: return None
            # Filter by remote_address_id
            sessions = self.nb.plugins.bgp.session.filter(remote_address_id=ip_obj.id)
            session_list = list(sessions)
            return session_list[0] if session_list else None
        except Exception: return None

    def create_bgp_session(self, 
                           name: str, 
                           site_id: int, 
                           device_id: int, 
                           local_ip_id: int, 
                           remote_ip_id: int, 
                           local_as_id: int, 
                           remote_as_id: int, 
                           tenant_id: int,
                           peer_group_id: int,
                           address_family: str, 
                           as_set: str = "",
                           prefix_limit: int = 0,
                           sync_pdb: bool = False,
                           md5_key: str = "",
                           peer_type: str = "peer_ixp",
                           description: str = "") -> object:
        
        #Creates a BGP Session with full custom fields support.
        try:
            limit_val = int(prefix_limit)
        except (ValueError, TypeError):
            limit_val = 0

        # Custom Fields Construction
        custom_fields = {
            "address_family": address_family,
            "peer_type": peer_type,
            "sync_from_pdb": sync_pdb,
            "bfd": False,
            "drained": False,
            "gtsm": False,
            "hide_peer_ip": False,
            "localpref": 100,
            "origin_as_filter_mode": "disable",
            "rtbh_filter": True
        }
        
        # Opcionális mezők
        if as_set:
            custom_fields["as_set"] = as_set
            
        if limit_val > 0:
            custom_fields["prefix_limit"] = limit_val
            
        if md5_key:
            custom_fields["md5"] = md5_key

        data = {
            "name": name,
            "status": "active",
            "site": site_id,
            "device": device_id,
            "local_address": local_ip_id,
            "remote_address": remote_ip_id,
            "local_as": local_as_id,
            "remote_as": remote_as_id,
            "tenant": tenant_id,
            "peer_group": peer_group_id,
            "description": description,
            "custom_fields": custom_fields
        }

        return self.nb.plugins.bgp.session.create(**data)