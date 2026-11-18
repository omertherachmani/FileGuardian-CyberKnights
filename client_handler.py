import threading
import socket
import datetime
from network_server import NetworkServer
from protocol import Protocol
from protocol_message import ProtocolMessage
from protocol_error import ProtocolError


class ClientHandler(threading.Thread):

    TIME_FORMAT = "%H:%M:%S"

    # שמות הפקודות והתגובות
    PING = "PING"
    ECHO = "ECHO"
    TIME = "TIME"
    EXIT = "EXIT"
    ERROR = "ERROR"
    CLIENTS = "CLIENTS"
    REPLY_PONG = "PONG"
    REPLY_BYE = "BYE"


    def __init__(self, client_socket: socket.socket, address: tuple, server: NetworkServer):
        super().__init__()
        self.__sock = client_socket
        self.__address = address
        self.__server = server
        self.name = f"Client {address[0]}:{address[1]}"

    def run(self):
        try:
            self.__serve()

        finally:
            self.__server.remove_handler(self)

    def __serve(self):

        with self.__sock:
            try:
                while True:
                    try:
                        request = Protocol.receive(self.__sock)

                        if request is None:
                            break

                    except ProtocolError as e:  # הזרם מסונכרן, אפשר להמשיך
                        if not self.__reply(ProtocolMessage(self.ERROR, str(e))):
                            break
                        continue

                    status = self.__reply(self.__process(request))

                    if request.command == self.EXIT or not status:
                        break

            except (ConnectionError, ValueError,OSError) as e:  # ניתוק או הפרה שאין ממנה התאוששות
                print(f"Error:{e}")

    def __process(self, msg: ProtocolMessage) -> ProtocolMessage:
        """מתרגם בקשה לתגובה. פקודה לא מוכרת -> הודעת ERROR."""

        command = msg.command

        if command not in Protocol.COMMANDS:
            return ProtocolMessage(self.ERROR, f"Unknown command: {command}")

        if command == self.PING:
            return ProtocolMessage(self.PING, self.REPLY_PONG)

        if command == self.ECHO:
            return ProtocolMessage(self.ECHO, msg.data)

        if command == self.TIME:
            return ProtocolMessage(self.TIME,
                                   datetime.datetime.now().strftime(self.TIME_FORMAT))
        if command == self.EXIT:
            return ProtocolMessage(self.EXIT, self.REPLY_BYE)

        if command == self.CLIENTS:
            return ProtocolMessage(self.CLIENTS, str(self.__server.client_count()))

        return ProtocolMessage(self.ERROR, f"Unknown command: {command}")

    def __reply(self, message: ProtocolMessage) -> bool:
        try:
            Protocol.send(self.__sock, message)
            return True
        except (ConnectionError, OSError):
            return False

    def stop(self):
        try:
            self.__sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass