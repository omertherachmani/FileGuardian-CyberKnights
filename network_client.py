import socket
from protocol import Protocol
from protocol_error import ProtocolError
from protocol_message import ProtocolMessage
from threading import Lock

class NetworkClient:

    #קבועים
    CONNECT_TIMEOUT = 5
    REPLY_TIMEOUT = 10
    DEFAULT_IP = "127.0.0.1"
    DEFAULT_PORT = 1729
    EXIT = "EXIT"


    def __init__(self, host = DEFAULT_IP, port = DEFAULT_PORT):
        """פעולה בונה למחלקה: שומר את כתובת השרת והפורט ויוצר socket"""

        self.__host = host
        self.__port = port
        self.lock : Lock = Lock()
        self.sock : socket.socket = socket.socket()
        self.__connected : bool = False
        self.address : tuple[str, int] = (host, port)

        try:
            self.sock.settimeout(self.CONNECT_TIMEOUT)
            self.sock.connect(self.address)
            self.__connected = True
        except OSError:
            self.close()
            raise

    @property
    def connected(self) -> bool:
        return self.__connected

    def request(self, message: ProtocolMessage) -> ProtocolMessage:
        with self.lock:
            if not self.__connected:
                raise ConnectionError("The Client isn't connected")

            try:
                # define wait time for a response
                self.sock.settimeout(self.REPLY_TIMEOUT)

                # send request and receive an answer
                Protocol.send(self.sock, message)
                response = Protocol.receive(self.sock)


                if response is None:
                    self._close_unlocked()
                    raise ConnectionError("Connection is closed due to ")


                if message.command == "EXIT" or response.command == "BYE":
                    self._close_unlocked()

                return response

            except socket.timeout as err:

                self._close_unlocked()
                raise TimeoutError("תם הזמן להמתנה לתשובה מהשרת.") from err

            except (OSError, ProtocolError):

                self._close_unlocked()
                raise

    def close(self) -> None:
        with self.lock:
            self._close_unlocked()

    def _close_unlocked(self) -> None:
        self.__connected = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass

    def run(self):
        """
        מנהל את התקשורת מול השרת בלולאה עד שהלקוח שולח EXIT.
        הלקוח שולח פקודה לשרת, הופך אותה להודעת פרוטוקול, שולח ומציג את תגובות השרת.
        כשהחיבור מתנתק (המשתמש מאזין EXIT) אז הסוקט של הלקוח נסגר לבסוף
        """
        try:
            #הלקוח מנסה להתחבר לשרת
            self.sock.connect((self.__host, self.__port))


            while True:

                request = input("Enter command:\n> ")

                #הופכים את ההודעה לאובייקט מסוג ProtocolMessage
                try:
                    protocol_request = ProtocolMessage.from_user_input(request)
                except ValueError as e:
                    print(f"Invalid input: {e}")
                    continue

                #שליחת ההודעה המקודדת דרך הsocket לשרת
                Protocol.send(self.sock, protocol_request)

                #קבלת הודעת תשובה מהשרת ופענוח בעזרת המחלקה Protocol
                server_msg = Protocol.receive(self.sock)

                print(server_msg)

                #תנאי עצירה
                if protocol_request.command == self.EXIT:
                    break

        #טיפול בשגיאות ניתוק
        except ConnectionError as e:
            print(f"Client connection error: {e}")

        except Exception as e:
            print(f"Error: {e}")

        #לבסוף סוגרים את הsocket
        finally:
            self.sock.close()

if __name__ == "__main__":
    client = NetworkClient()
    client.run()
