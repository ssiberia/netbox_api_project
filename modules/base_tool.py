from abc import ABC, abstractmethod

class BaseTool(ABC):
    """
    Ez az 'Absztrakt Ős'. Nem csinál semmit, csak előírja a szabályokat.
    Minden jövőbeli menüpontnak ebből KELL származnia.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Ezt a nevet fogjuk kiírni a Főmenüben."""
        pass

    @abstractmethod
    def run(self):
        """Ez a függvény indul el, amikor a felhasználó kiválasztja."""
        pass