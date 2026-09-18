"""
IVACS V-TRACE Abstract Vehicle Registry Base Class
Defines the uniform interface for querying vehicle registration databases.
"""

from abc import ABC, abstractmethod
from typing import Optional
from backend.vehicle_registry.schemas import VehicleRegistryRecord

class VehicleRegistry(ABC):
    """
    Abstract vehicle registry contract.
    Both DemoVehicleRegistry and future VahanVehicleRegistry implement this interface.
    """

    @abstractmethod
    def get_vehicle_by_plate(self, plate: str) -> Optional[VehicleRegistryRecord]:
        """
        Retrieves registration profile for a given plate.
        Returns VehicleRegistryRecord if found, else None.
        """
        pass
