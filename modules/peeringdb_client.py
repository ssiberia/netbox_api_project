import requests
from typing import Optional, Dict, List, Any

class PeeringDBClient:

    # interact with the public PeeringDB API.
    BASE_URL = "https://www.peeringdb.com/api"

    def get_asn_details(self, asn: int) -> Optional[Dict[str, Any]]:

        # Fetch ASN details, prefix limits, and IRR AS-SET
        url = f"{self.BASE_URL}/net"
        params = {"asn": asn}

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data['data']:
                # return the first matching network object
                return data['data'][0]
            return None

        except requests.RequestException as e:
            print(f"Error fetching data from PeeringDB: {e}")
            return None

    def get_ixp_presence(self, asn: int) -> List[Dict[str, Any]]:
        """
        Fetches all IXP connections (netixlan) for a given ASN.
        Returns a list of dictionaries containing IXP name, IP addresses
        """
        url = f"{self.BASE_URL}/netixlan"
        params = {"asn": asn}
        ixp_list = []

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data['data']:
                for entry in data['data']:
                    ixp_list.append({
                        "id": entry["id"],
                        "ix_name": entry["name"],  # e.g., "DE-CIX Frankfurt"
                        "ix_id": entry["ix_id"],   # PeeringDB ID of the IXP
                        "ipaddr4": entry["ipaddr4"],
                        "ipaddr6": entry["ipaddr6"],
                        "asn": entry["asn"]
                    })
            
            # Sort alphabetically by IXP name for a better output
            return sorted(ixp_list, key=lambda x: x['ix_name'])

        except requests.RequestException as e:
            print(f"Error fetching IXP data: {e}")
            return []