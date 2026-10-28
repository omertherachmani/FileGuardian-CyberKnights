import socket
from typing import Literal

from protocol_message import ProtocolMessage


class Protocol:
    """
    העברת הודעות שלמות על גבי TCP.
    TCP הוא זרם בתים ללא גבולות הודעות, ולכן כל הודעה נשלחת עם כותרת אורך
    בת 4 בתים (big-endian) ונקראת בדיוק לפי האורך שבכותרת.
    """

    # --- קבועי מחלקה ---
    HEADER_SIZE = 4
    BYTE_ORDER: Literal["big", "little"] = "big"
    MAX_LENGTH = 2 ** 16
    COMMANDS = ["PING", "ECHO", "TIME", "EXIT"]


    @staticmethod
    def send(sock: socket.socket, message: ProtocolMessage) -> None:
        """
        מקודד הודעה, מוסיף כותרת אורך ושולח את כל הבתים באמצעות sendall.
        מעלה ValueError אם גוף ההודעה גדול מ-MAX_LENGTH.
        """

        body_bytes = message.to_bytes()

        if len(body_bytes) > Protocol.MAX_LENGTH:
            raise ValueError(f"Message size ({len(body_bytes)}) exceeds MAX_LENGTH ({Protocol.MAX_LENGTH})")

        header = len(body_bytes).to_bytes(Protocol.HEADER_SIZE, byteorder=Protocol.BYTE_ORDER)
        sock.sendall(header + body_bytes)


    @staticmethod
    def receive(sock: socket.socket) -> ProtocolMessage:
        """
        קורא הודעה שלמה: כותרת אורך ואז גוף באורך המדויק.
        מעלה ConnectionError אם החיבור נסגר, ValueError אם האורך חורג מ-MAX_LENGTH,
        ו-ProtocolError אם הגוף אינו הודעה תקינה.
        """

        header_bytes = Protocol.__recv_exact(sock, Protocol.HEADER_SIZE)

        message_length = int.from_bytes(header_bytes, byteorder=Protocol.BYTE_ORDER)

        if message_length > Protocol.MAX_LENGTH:
            raise ValueError(f"Incoming message size ({message_length}) exceeds MAX_LENGTH ({Protocol.MAX_LENGTH})")

        body_bytes = Protocol.__recv_exact(sock, message_length)

        return ProtocolMessage.from_bytes(body_bytes)


    @staticmethod
    def __recv_exact(sock: socket.socket, n: int) -> bytes:
        """
        פעולת עזר פרטית: אוספת בדיוק n בתים מהשקע באמצעות קריאות recv חוזרות.
        מעלה ConnectionError אם החיבור נסגר לפני שנקראו כל n הבתים.
        """

        data = bytearray()

        while len(data) < n:
            packet = sock.recv(n - len(data))

            if not packet:
                raise ConnectionError("Connection closed")

            data.extend(packet)

        return bytes(data)
