from dataclasses import dataclass

from .metadata import MetadataParser, MessageMetadata


@dataclass(frozen=True)
class Message:
    metadata: MessageMetadata
    payload: bytes = b""


class MessageParser:

    @staticmethod
    def parse(raw: bytes) -> Message:
        metadata_length = int.from_bytes(raw[:4], "big")

        if metadata_length > len(raw):
            raise ValueError("Invalid metadata length")

        metadata = MetadataParser.parse(raw)
        payload = raw[metadata_length:]

        return Message(
            metadata=metadata,
            payload=payload,
        )

    @staticmethod
    def serialize(message: Message) -> bytes:
        metadata = MetadataParser.serialize(message.metadata)
        return metadata + message.payload
