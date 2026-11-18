import socket
from typing import List, Literal, Optional


class ProtocolError(Exception):
    """
    חריגה ייעודית לדיווח על הודעה שאינה עומדת בפורמט הפרוטוקול
    (קידוד שגוי, מפריד חסר, פקודה ריקה וכדומה).
    """
    pass


class ProtocolMessage:
    """
    הודעה אחת בפרוטוקול: שם פקודה ותוכן, בפורמט COMMAND|data בקידוד UTF-8.
    משמשת גם לבקשות (לקוח -> שרת) וגם לתגובות (שרת -> לקוח).
    """


    SEPARATOR = "|"
    ENCODING = "utf-8"


    def __init__(self, command: str, data: str = "") -> None:
        """
        יוצר הודעה: מנרמל את שם הפקודה לאותיות גדולות ומוודא שהיא אינה ריקה
        ואינה מכילה מפריד.

        :param command: שם הפקודה
        :param data: תוכן ההודעה (יכול להכיל את תו המפריד)
        :raises ValueError: אם הפקודה ריקה או מכילה מפריד
        """

        if not command:
            raise ValueError("the command cannot be empty")

        if self.SEPARATOR in command:
            raise ValueError("the command cannot have a separator (|)")

        self.__command: str = command.upper()
        self.__data: str = data


    @property
    def command(self) -> str:
        """שם הפקודה (באותיות גדולות), לקריאה בלבד."""

        return self.__command


    @property
    def data(self) -> str:
        """תוכן ההודעה, לקריאה בלבד."""

        return self.__data


    def to_bytes(self) -> bytes:
        """
        בונה את הטקסט COMMAND|data ומקודד אותו לבתים ב-UTF-8.

        :return: ההודעה בבתים
        """

        text = f"{self.__command}{self.SEPARATOR}{self.__data}"
        return text.encode(self.ENCODING)


    @classmethod
    def from_bytes(cls, raw: bytes) -> "ProtocolMessage":
        """
        מפענח בתים (UTF-8), מפצל במפריד הראשון בלבד ובונה הודעה.
        הפיצול הראשון בלבד מאפשר ל-data להכיל את תו המפריד.

        :param raw: הבתים שהתקבלו (גוף הודעה אחד שלם)
        :return: ההודעה המפוענחת
        :raises ProtocolError: אם הקידוד שגוי, המפריד חסר או הפקודה אינה תקינה
        """

        try:
            text = raw.decode(cls.ENCODING)
        except UnicodeDecodeError as e:
            raise ProtocolError(f"Invalid {cls.ENCODING} data") from e

        if cls.SEPARATOR not in text:
            raise ProtocolError("a SEPARATOR is missing")

        command, data = text.split(cls.SEPARATOR, 1)

        try:
            return cls(command, data)
        except ValueError as e:
            raise ProtocolError(str(e)) from e


    @classmethod
    def from_user_input(cls, line: str) -> "ProtocolMessage":
        """
        מפריד קלט משתמש לשם פקודה ולתוכן אופציונלי (עד הרווח הראשון).

        :param line: השורה שהמשתמש הקליד, למשל "ECHO שלום"
        :return: הודעת פרוטוקול
        :raises ValueError: אם הקלט ריק
        """

        line = line.strip()

        text_parts = line.split(" ", 1)
        command = text_parts[0]

        if len(text_parts) > 1:
            data = text_parts[1]
        else:
            data = ""

        return cls(command, data)


    def __eq__(self, other) -> bool:
        """משווה שתי הודעות לפי שם הפקודה והתוכן."""

        if not isinstance(other, ProtocolMessage):
            return NotImplemented

        return self.__command == other.command and self.__data == other.data


    def __repr__(self) -> str:
        """ייצוג מפורט של ההודעה לצורכי פיתוח ואיתור תקלות."""

        return f"ProtocolMessage(command={self.command!r}, data={self.data!r})"


    def __str__(self) -> str:
        """תיאור קריא של הפקודה והתוכן להצגה."""

        return f"{self.command}{self.SEPARATOR}{self.data}"


class Protocol:
    """
    העברת הודעות שלמות על גבי TCP.
    TCP הוא זרם בתים ללא גבולות הודעות, ולכן כל הודעה נשלחת עם כותרת אורך
    בת 4 בתים (big-endian) ונקראת בדיוק לפי האורך שבכותרת.
    המחלקה משותפת לשרת וללקוח.
    """

    # --- קבועי מחלקה ---
    HEADER_SIZE: int = 4
    BYTE_ORDER: Literal["big", "little"] = "big"
    # כותרת של 4 בתים יכולה לייצג עד 2**32-1, אבל מגבילים לערך סביר (1MB)
    # כדי ששרת לא ימתין לגוף של 4GB מלקוח זדוני או פגום.
    MAX_LENGTH: int = 1024 * 1024
    # הפקודות המוכרות בפרוטוקול
    COMMANDS: List[str] = ["PING", "ECHO", "TIME", "EXIT", "CLIENTS"]
    # הפקודות שדורשות נתונים (ה-UI מציג שדה נתונים רק עבורן)
    COMMANDS_WITH_DATA: List[str] = ["ECHO"]


    @staticmethod
    def send(sock: socket.socket, message: ProtocolMessage) -> None:
        """
        מקודד הודעה, מוסיף כותרת אורך ושולח את כל הבתים באמצעות sendall.

        :param sock: השקע לשליחה
        :param message: ההודעה לשליחה
        :raises ValueError: אם גוף ההודעה גדול מ-MAX_LENGTH (לא נשלח דבר)
        """

        body_bytes = message.to_bytes()

        if len(body_bytes) > Protocol.MAX_LENGTH:
            raise ValueError(f"Message size ({len(body_bytes)}) exceeds MAX_LENGTH ({Protocol.MAX_LENGTH})")

        header = len(body_bytes).to_bytes(Protocol.HEADER_SIZE, byteorder=Protocol.BYTE_ORDER)
        sock.sendall(header + body_bytes)


    @staticmethod
    def receive(sock: socket.socket) -> Optional[ProtocolMessage]:
        """
        קורא הודעה שלמה: כותרת אורך ואז גוף באורך המדויק.

        :param sock: השקע לקריאה
        :return: ההודעה, או None אם הצד השני התנתק
        :raises ValueError: אם האורך שבכותרת חורג מ-MAX_LENGTH (הזרם כבר לא מסונכרן)
        :raises ProtocolError: אם הגוף נקרא במלואו אבל אינו הודעה תקינה (הזרם מסונכרן)
        """

        header_bytes = Protocol._recv_exact(sock, Protocol.HEADER_SIZE)

        if header_bytes is None:
            return None

        message_length = int.from_bytes(header_bytes, byteorder=Protocol.BYTE_ORDER)

        if message_length > Protocol.MAX_LENGTH:
            raise ValueError(f"Incoming message size ({message_length}) exceeds MAX_LENGTH ({Protocol.MAX_LENGTH})")

        body_bytes = Protocol._recv_exact(sock, message_length)

        if body_bytes is None:
            return None

        return ProtocolMessage.from_bytes(body_bytes)


    @staticmethod
    def _recv_exact(sock: socket.socket, n: int) -> Optional[bytes]:
        """
        פעולת עזר: אוספת בדיוק n בתים מהשקע באמצעות קריאות recv חוזרות
        (TCP יכול להחזיר רק חלק מהבתים בכל קריאה).

        :param sock: השקע לקריאה
        :param n: מספר הבתים לקריאה
        :return: n בתים, או None אם החיבור נסגר לפני שנקראו כולם
        """

        data = bytearray()

        while len(data) < n:
            packet = sock.recv(n - len(data))

            if not packet:
                return None

            data.extend(packet)

        return bytes(data)
