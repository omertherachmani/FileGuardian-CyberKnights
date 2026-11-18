import threading
import socket
import datetime
from typing import TYPE_CHECKING

from protocol import Protocol, ProtocolMessage, ProtocolError

if TYPE_CHECKING:
    # נטען רק לצורכי בדיקת טיפוסים; ייבוא רגיל היה יוצר ייבוא מעגלי עם network_server
    from network_server import NetworkServer


class ClientHandler(threading.Thread):
    """
    מטפל בלקוח יחיד, ב-Thread משלו.

    השרת יוצר handler לכל חיבור חדש. ה-handler קורא הודעות מהלקוח,
    מעבד אותן ושולח תגובות עד שהלקוח שולח EXIT או מתנתק.
    בסוף הריצה הוא סוגר את ה-socket ומסיר את עצמו מהשרת.
    """


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

    # הודעות שגיאה
    MSG_UNKNOWN_COMMAND = "Unknown command: {}"


    def __init__(self, client_socket: socket.socket, address: tuple, server: "NetworkServer") -> None:
        """
        :param client_socket: ה-socket של הלקוח
        :param address: כתובת הלקוח (ip, port), לצורכי לוגים
        :param server: השרת שיצר את ה-handler (לצורך remove_handler ו-client_count)
        """

        super().__init__()
        self.__sock = client_socket
        self.__address = address
        self.__server = server
        # שם ה-Thread משמש בלוגים
        self.name = f"Client {address[0]}:{address[1]}"


    def run(self) -> None:
        """
        נקודת הכניסה של ה-Thread (נקראת אוטומטית על ידי start).

        ב-finally ה-handler מסיר את עצמו מהשרת, גם אם הייתה שגיאה.
        """

        print(f"- {self.name}: Connected")

        try:
            self.__serve()

        finally:
            self.__server.remove_handler(self)
            print(f"- {self.name}: Disconnected")


    def __serve(self) -> None:
        """
        לולאת הטיפול בלקוח: קבלה, עיבוד ושליחת תגובה.

        נגמרת כשהלקוח שולח EXIT, מתנתק, או כששליחה נכשלת.
        ה-with סוגר את ה-socket בסוף.
        """

        with self.__sock:
            try:

                while True:
                    try:
                        request = Protocol.receive(self.__sock)

                        if request is None:
                            break

                    # ProtocolError נזרקת רק אחרי שהגוף נקרא במלואו, לכן הזרם מסונכרן ואפשר להמשיך
                    except ProtocolError as e:
                        print(f"- {self.name}: Protocol error - {e}")

                        if not self.__reply(ProtocolMessage(self.ERROR, str(e))):
                            break
                        continue

                    status = self.__reply(self.__process(request))

                    if request.command == self.EXIT or not status:
                        break

            # ConnectionError הוא תת-סוג של OSError ולכן מכוסה כאן.
            # ValueError: כותרת עם אורך שחורג מ-MAX_LENGTH, הזרם לא מסונכרן ולכן מנתקים
            except (ValueError, OSError) as e:
                print(f"- {self.name}: Error - {e}")


    def __process(self, msg: ProtocolMessage) -> ProtocolMessage:
        """
        מפיק תגובה להודעה שהתקבלה.

        :param msg: ההודעה מהלקוח
        :return: ההודעה לשליחה חזרה (ERROR אם הפקודה לא מוכרת)
        """

        command = msg.command

        if command not in Protocol.COMMANDS:
            return ProtocolMessage(self.ERROR, self.MSG_UNKNOWN_COMMAND.format(command))

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

        # פקודה שנמצאת ב-COMMANDS אבל אין לה טיפול כאן
        return ProtocolMessage(self.ERROR, self.MSG_UNKNOWN_COMMAND.format(command))


    def __reply(self, message: ProtocolMessage) -> bool:
        """
        שולח הודעה ללקוח.

        :param message: ההודעה לשליחה
        :return: True אם נשלחה, False אם הייתה בעיית חיבור
        """

        try:
            Protocol.send(self.__sock, message)
            return True

        except OSError:  # כולל ConnectionError
            return False


    def stop(self) -> None:
        """
        עוצר את ה-handler מבחוץ (נקרא על ידי השרת בזמן סגירה).

        shutdown על ה-socket משחרר את ה-recv החסום ב-__serve,
        וכך ה-Thread יוצא מהלולאה ומסתיים.
        """

        try:
            self.__sock.shutdown(socket.SHUT_RDWR)

        except OSError:
            pass
