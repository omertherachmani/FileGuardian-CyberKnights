SEPARATOR = "|"
ENCODING = "utf-8"
class ProtocolMessage:
    HEADER_SIZE = 4  # MAX_LENGTH = 2 ** (8 * HEADER_SIZE) - 1    # largest length

    COMMANDS = ["TIME", "ECHO", "PING", "EXIT"]

    SEPARATOR = "|"
    ENCODING = "utf-8"

    def __init__(self, command: str, data=""):
        if not command:
            raise ValueError("the commend cannot be empty")

        if self.SEPARATOR in command:
            raise ValueError("the command cannot have a separator (|)")
        self.__command = command.upper()
        self.__data = data

    @property
    def command(self):
        return self.__command

    @property
    def data(self):
        return self.__data

    def to_bytes(self) -> bytes:
        text = f"{self.__command}{self.SEPARATOR}{self.__data}"
        encoded_text = text.encode(self.ENCODING)
        return encoded_text

    @classmethod
    def from_bytes(cls, raw) -> "ProtocolMessage":
        try:
            text = raw.decode(ENCODING)
        except Exception as e:
            raise ValueError(f"Failed to decode bytes with {ENCODING}: {e}")

        if SEPARATOR not in text:
            raise ValueError("Error: a SEPARATOR is missing")

        command, data = text.split(SEPARATOR)
        return cls(command, data)

    @classmethod
    def from_user_input(cls, user_input: str) -> "ProtocolMessage":
        user_input = user_input.strip()

        text_parts = user_input.split(" ", 1)
        command = text_parts[0]

        if len(text_parts) > 1:
            data = text_parts[1]
        else:
            data = ""

        return cls(command, data)

    def __eq__(self, other) -> bool:
        return self.__command == other.command and self.__data == other.data

    def __repr__(self) -> str:
        return f"ProtocolMessage(command={self.command!r}, data={self.data!r})"

    def __str__(self) -> str:
        return f"Command: {self.command}, Data: {self.data}"