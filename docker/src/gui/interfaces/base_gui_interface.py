from abc import ABC, abstractmethod

class BaseGUIInterface(ABC):
    @abstractmethod
    def start(self):
        """Start the GUI application."""
        pass
    
    @abstractmethod
    def stop(self):
        """Stop the GUI application."""
        pass
    
    @abstractmethod
    def cleanup(self):
        """Clean up resources used by the GUI application."""
        pass