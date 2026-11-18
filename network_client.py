import socket
from threading import Lock

from protocol import Protocol, ProtocolMessage, ProtocolError


class NetworkClient:
    """
    לקוח TCP לשימוש חוזר, גם ממסוף (run) וגם מה-UI (request).

    מתחבר לשרת בבנאי ושומר את מצב החיבור. כל בקשה נשלחת ונענית תחת Lock
    כדי שבקשות מכמה threads לא יתערבבו על אותו חיבור.
    אחרי שגיאה, timeout או EXIT החיבור נסגר ולא משתמשים בו שוב.
    """


    # קבועים
    CONNECT_TIMEOUT: int = 5     # כמה שניות מחכים להתחברות לשרת
    REPLY_TIMEOUT: int = 10      # כמה שניות מחכים לתשובה מהשרת
    DEFAULT_IP = "127.0.0.1"
    DEFAULT_PORT = 8000
    EXIT = "EXIT"


    def __init__(self, ip: str = DEFAULT_IP, port: int = DEFAULT_PORT) -> None:
        """
        יוצר את ה-socket ומתחבר לשרת.

        :param ip: כתובת השרת
        :param port: הפורט של השרת
        :raises OSError: אם ההתחברות נכשלה או שנגמר הזמן (ה-socket נסגר לפני כן)
        """

        self.__lock: Lock = Lock()
        self.__sock: socket.socket = socket.socket()
        self.__connected: bool = False
        self.__address: tuple = (ip, port)

        try:
            self.__sock.settimeout(self.CONNECT_TIMEOUT)
            self.__sock.connect(self.__address)
            self.__connected = True

        except OSError:
            self.close()
            raise


    @property
    def connected(self) -> bool:
        """האם החיבור לשרת פעיל, לקריאה בלבד."""

        return self.__connected


    def request(self, message: ProtocolMessage) -> ProtocolMessage:
        """
        שולח הודעה לשרת ומחכה לתשובה, תחת Lock.

        אם הייתה שגיאה או timeout החיבור נסגר, כי אי אפשר לדעת מה מצב הזרם
        ולכן לא שולחים בו בקשה חדשה. גם אחרי EXIT החיבור נסגר.

        :param message: ההודעה לשליחה
        :return: תשובת השרת
        :raises ConnectionError: אם הלקוח לא מחובר או שהשרת סגר את החיבור
        :raises TimeoutError: אם התשובה לא הגיעה תוך REPLY_TIMEOUT שניות
        :raises ProtocolError: אם התשובה אינה הודעה תקינה
        :raises ValueError: אם ההודעה גדולה מדי (לא נשלח דבר והחיבור נשאר תקין)
        """

        with self.__lock:
            if not self.__connected:
                raise ConnectionError("The client isn't connected")

            try:
                self.__sock.settimeout(self.REPLY_TIMEOUT)

                Protocol.send(self.__sock, message)

                try:
                    response = Protocol.receive(self.__sock)

                except ValueError as err:
                    # אורך לא חוקי בכותרת: לא ידוע כמה בתים נשארו בזרם, החיבור לא אמין
                    self._close_unlocked()
                    raise ProtocolError(str(err)) from err

                if response is None:
                    self._close_unlocked()
                    raise ConnectionError("The server closed the connection")

                if message.command == self.EXIT:
                    self._close_unlocked()

                return response

            except socket.timeout as err:
                self._close_unlocked()
                raise TimeoutError("תם הזמן להמתנה לתשובה מהשרת.") from err

            except (OSError, ProtocolError):
                self._close_unlocked()
                raise


    def close(self) -> None:
        """סוגר את ה-socket ומסמן שהחיבור כבר לא פעיל. בטוחה לקריאה חוזרת."""

        with self.__lock:
            self._close_unlocked()


    def _close_unlocked(self) -> None:
        """
        סגירה בפועל, ללא נעילה (לשימוש פנימי כשה-Lock כבר מוחזק).
        מטפלת ב-OSError כדי שסגירה לא תפיל את הלקוח.
        """

        self.__connected = False

        try:
            self.__sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

        try:
            self.__sock.close()
        except OSError:
            pass


    def run(self) -> None:
        """
        ממשק מסוף: קורא פקודות מהמשתמש בלולאה עד EXIT או ניתוק.

        משתמש בחיבור שנוצר בבנאי ושולח דרך request, כך שמסוף ו-UI
        משתמשים באותה לוגיקה. בסוף סוגר את החיבור.
        """

        try:
            while self.__connected:
                line = input("Enter command:\n> ")

                try:
                    message = ProtocolMessage.from_user_input(line)

                except ValueError as e:
                    print(f"Invalid input: {e}")
                    continue

                try:
                    print(self.request(message))

                except ValueError as e:  # הודעה גדולה מדי, החיבור תקין
                    print(f"Invalid input: {e}")

        except (OSError, ProtocolError) as e:  # כולל ConnectionError ו-TimeoutError
            print(f"Client connection error: {e}")

        except (KeyboardInterrupt, EOFError):
            print("Client stopped by user")

        finally:
            self.close()


if __name__ == "__main__":
    client = NetworkClient()
    client.run()
