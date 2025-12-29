class BasePeeringController:
    """
    Ez az ŐS (Parent).
    Csak a közös szerszámokat kezeli (NetBox, PeeringDB),
    de nem tudja, hogyan kell konkrétan peeringelni.
    """
    def __init__(self, nb_client, pdb_client):
        self.nb = nb_client
        self.pdb = pdb_client
        self.target_asn = None