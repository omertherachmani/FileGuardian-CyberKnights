import socket
from typing import Literal
from Protocol_Message import ProtocolMessage

class Protocol:
    HEADER_SIZE = 4
    COMMANDS = ["PING", "ECHO", "TIME", "EXIT"]
    MAX_LENGTH = 2**16
    BYTE_ORDER: Literal["big", "little"] = "big"

    @staticmethod
    def send(sock, message : 'ProtocolMessage') -> None:
        body_bytes = message.to_bytes()
        if len(body_bytes) > Protocol.MAX_LENGTH:
            raise ValueError(f"Message size ({len(body_bytes)}) exceeds MAX_LENGTH ({Protocol.MAX_LENGTH})")
        header = len(body_bytes).to_bytes(Protocol.HEADER_SIZE, byteorder=Protocol.BYTE_ORDER)
        sock.sendall(header + body_bytes)

    @staticmethod
    def receive(sock) -> ProtocolMessage:

        # 1. קריאת 4 הבתים של כותרת האורך
        header_bytes = Protocol._recv_exact(sock, Protocol.HEADER_SIZE)
        if header_bytes is None:
            raise ConnectionError("Connection closed")

        # 2. המרת כותרת(header) הבתים למספר שלם (אורך גוף ההודעה)
        message_length = int.from_bytes(header_bytes, byteorder=Protocol.BYTE_ORDER)


        if message_length > Protocol.MAX_LENGTH:
            raise ValueError(f"Incoming message size ({message_length}) exceeds MAX_LENGTH ({Protocol.MAX_LENGTH})")

        # 4. קריאת גוף ההודעה המלא בדיוק לפי האורך שפוענח מהכותרת
        body_bytes = Protocol._recv_exact(sock, message_length)
        if body_bytes is None:
            raise ConnectionError("Connection closed")

        return ProtocolMessage.from_bytes(body_bytes)
    @staticmethod
    def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
        """
        פעולת עזר פרטית: אוספת בדיוק n בתים מתוך השקע באמצעות קריאות recv חוזרות.
        מחזירה None אם החיבור נסגר לפני השלמת הקריאה.
        """
        data = bytearray()
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                raise ConnectionError("Connection closed") # הנתק התרחש לפני שנקראו כל n הבתים
            data.extend(packet)
        return bytes(data)


class ProtocolError(Exception):
    pass

