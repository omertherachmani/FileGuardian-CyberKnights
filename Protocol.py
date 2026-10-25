class Protocol:
    def __init__(self, command, data):
        self.__command = command
        self.__data = data


    def from_bytes(self):
        return self.__data.decode()

    def to_bytes(self):
        return self.__data.encode()

