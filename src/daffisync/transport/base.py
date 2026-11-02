from abc import ABCMeta, abstractmethod
from typing import Hashable, Any


class TransportBase(metaclass=ABCMeta):

    @property
    @abstractmethod
    def identity(self) -> Hashable:
        """Unique identity of the transport configuration."""
        ...

    @abstractmethod
    def create_transport(self) -> Any:
        """Create the underlying transport implementation."""
        ...
