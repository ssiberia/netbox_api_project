from abc import ABC, abstractmethod
import re

class NamingStrategy(ABC):
    """
    Ez a közös 'Interface'. Minden jövőbeli név-tisztító stratégiának
    tudnia kell a 'sanitize' parancsot.
    """
    @abstractmethod
    def sanitize(self, name: str) -> str:
        pass

# --- 1. Stratégia: A szigorú (amit eddig használtál) ---
class StrictAlphanumericStrategy(NamingStrategy):
    """
    Mindent kitöröl, ami nem betű vagy szám.
    Pl: "IT.Gate S.p.A." -> "ITGateSpA"
    """
    def sanitize(self, name: str) -> str:
        return re.sub(r'[^a-zA-Z0-9]', '', name)

# --- 2. Stratégia: Egy lazább (példa a jövőre) ---
class UnderscoreStrategy(NamingStrategy):
    """
    A speciális karaktereket aláhúzásra cseréli.
    Pl: "IT.Gate S.p.A." -> "IT_Gate_S_p_A"
    """
    def sanitize(self, name: str) -> str:
        # Cseréljünk mindent, ami nem karakter/szám, aláhúzásra
        clean = re.sub(r'[^a-zA-Z0-9]', '_', name)
        # Szedjük ki a duplikált aláhúzásokat (pl. "__")
        return re.sub(r'_+', '_', clean).strip('_')