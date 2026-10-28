from tkinter.constants import SEPARATOR

from protocol_error import ProtocolError


class ProtocolMessage:
    """
        הודעה אחת בפרוטוקול: שם פקודה ותוכן, בפורמט COMMAND|data בקידוד UTF-8.
        משמשת גם לבקשות (לקוח -> שרת) וגם לתגובות (שרת -> לקוח).
        """


    SEPARATOR = "|"
    ENCODING = "utf-8"


    def __init__(self, command: str, data=""):
        """
                יוצר הודעה: מנרמל את שם הפקודה לאותיות גדולות ומוודא שהיא אינה ריקה
                ואינה מכילה מפריד. אחרת מעלה ValueError.
                """

        if not command:
            raise ValueError("the commend cannot be empty")

        if self.SEPARATOR in command:
            raise ValueError("the command cannot have a separator (|)")

        self.__command: str = command.upper()
        self.__data: str = data


    @property
    def command(self):
        """שם הפקודה (באותיות גדולות), לקריאה בלבד."""

        return self.__command


    @property
    def data(self):
        """תוכן ההודעה, לקריאה בלבד."""
        return self.__data


    def to_bytes(self) -> bytes:
        """בונה את הטקסט COMMAND|data ומקודד אותו לבתים ב-UTF-8."""

        text = f"{self.__command}{self.SEPARATOR}{self.__data}"
        encoded_text = text.encode(self.ENCODING)
        return encoded_text


    @classmethod
    def from_bytes(cls, raw) -> "ProtocolMessage":
        """
                מפענח בתים (UTF-8), מפצל במפריד הראשון בלבד ובונה הודעה.
                הפיצול הראשון בלבד מאפשר ל-data להכיל את תו המפריד.
                מעלה ProtocolError אם הקידוד שגוי, המפריד חסר או הפקודה אינה תקינה.
                """

        try:
            text = raw.decode(cls.ENCODING)
        except UnicodeDecodeError as e:
            raise ProtocolError(f"Invalid {cls.ENCODING} data") from e

        if cls.SEPARATOR not in text:
            raise ValueError("Error: a SEPARATOR is missing")

        command, data = text.split(cls.SEPARATOR, 1)

        try:
            return cls(command, data)
        except ValueError as e:
            raise ProtocolError(str(e)) from e


    @classmethod
    def from_user_input(cls, user_input: str) -> "ProtocolMessage":
        """
                מפריד קלט משתמש לשם פקודה ולתוכן אופציונלי (עד הרווח הראשון).
                מעלה ValueError אם הקלט ריק.
                """

        user_input = user_input.strip()

        text_parts = user_input.split(" ", 1)
        command = text_parts[0]

        if len(text_parts) > 1:
            data = text_parts[1]
        else:
            data = ""

        return cls(command, data)


    def __eq__(self, other) -> bool:
        """משווה שתי הודעות לפי שם הפקודה והתוכן."""

        return self.__command == other.command and self.__data == other.data


    def __repr__(self) -> str:
        """ייצוג מפורט של ההודעה לצורכי פיתוח ואיתור תקלות."""

        return f"ProtocolMessage(command={self.command!r}, data={self.data!r})"


    def __str__(self) -> str:
        """תיאור קריא של הפקודה והתוכן להצגה."""

        return f"{self.command}:{self.data}"