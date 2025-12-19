import pynetbox
import os
from typing import List, Optional

class NetBoxClient:
    """
    Main NetBox API Wrapper.
    Handles Authentication, Tenancy, ASN and BGP helper lookups.
    """
    def __init__(self):
        url = os.getenv("NETBOX_URL")
        token = os.getenv("NETBOX_TOKEN")
        if not url or not token:
            raise ValueError("Missing NETBOX_URL or NETBOX_TOKEN env vars")
        self.nb = pynetbox.api(url, token=token)

    def get_tenant_by_name(self, name_fragment: str) -> List[object]:
        """Searches for tenants using NetBox 'q' search + Python filtering."""
        if not name_fragment: return []
        try:
            api_results = self.nb.tenancy.tenants.filter(q=name_fragment)
            return [t for t in api_results if name_fragment.lower() in t.name.lower() or name_fragment.lower() in t.slug.lower()]
        except Exception: return []

    def get_asn_for_tenant(self, asn: int, tenant_id: int) -> Optional[object]:
        """
        Checks if the ASN object exists AND belongs to the specific Tenant.
        Returns the AS object if found, None otherwise.
        """
        try:
            # Filter for AS and Tenant
            res = self.nb.ipam.asns.filter(asn=asn, tenant_id=tenant_id)
            as_list = list(res)
            return as_list[0] if as_list else None
        except Exception:
            return None
            
    def get_my_asn_object(self, asn: int) -> Optional[object]:
        """
        Gets our own ASN object (e.g., 5405). This usually belongs to our own Tenant.
        """
        try:
            res = self.nb.ipam.asns.filter(asn=asn)
            as_list = list(res)
            return as_list[0] if as_list else None
        except Exception:
            return None

    def get_peer_group_id(self, name: str = "Peers") -> Optional[int]:
        """Finds the ID of a BGP Peer Group by name."""
        try:
            res = self.nb.plugins.bgp.peer_group.filter(name=name)
            pg_list = list(res)
            return pg_list[0].id if pg_list else None
        except Exception:
            return None
        