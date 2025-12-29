from typing import Optional, Dict

class IPManager:
    """
    Dedicated manager for IP Address operations in NetBox.
    Handles searching, validation, and creation.
    """
    def __init__(self, nb_client):
        self.nb = nb_client.nb

    def get_ip_address(self, address: str) -> Optional[object]:
        # Checks if an IP address exists in NetBox IPAM.
        return self.nb.ipam.ip_addresses.get(address=address)


    def get_prefix_for_ip(self, ip_address: str) -> Optional[object]:
        # Finds the parent Prefix for a given IP address.
        prefixes = self.nb.ipam.prefixes.filter(contains=ip_address)
        # sort by smallest mask size
        sorted_prefixes = sorted(prefixes, key=lambda p: int(str(p.prefix).split('/')[1]), reverse=True)
        # Return the longest prefix
        return sorted_prefixes[0] if sorted_prefixes else None


    def get_device_site_from_ip(self, ip_address: str) -> Optional[Dict]:
        # Tries to find the Device and Site associated with a Local IP.
        ip_obj = self.get_ip_address(ip_address)
        
        if not ip_obj or not ip_obj.assigned_object:
            return None
            
        interface = ip_obj.assigned_object
        
        # Check if it is a Device interface
        if hasattr(interface, 'device'):
            device = interface.device
            full_device = self.nb.dcim.devices.get(id=device.id)
            return {
                "device_id": full_device.id,
                "device_name": full_device.name,
                "site_id": full_device.site.id,
                "site_name": full_device.site.name
            }
        return None

    def create_ip_address(self, address: str, tenant_id: int, description: str = "") -> Optional[object]:
        #Creates a new IP Address object in NetBox based on company policy.
        data = {
            "address": address,
            "status": "active",
            "tenant": tenant_id,
            "description": description,
        }
        
        try:
            return self.nb.ipam.ip_addresses.create(**data)
        except Exception as e:
            raise e