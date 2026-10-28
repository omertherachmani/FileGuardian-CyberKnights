import socket
from datetime import datetime

from protocol import Protocol
from protocol_error import ProtocolError
from protocol_message import ProtocolMessage


class NetworkServer:
    """
    צד השרת: מקבל לקוח אחד (accept יחיד), קורא בקשות, מחזיר תגובות וסוגר.
    השרת אחראי רק על תקשורת והחלטה מה להחזיר; הקידוד והמסגור (framing)
    נמצאים ב-ProtocolMessage וב-Protocol.
    """

    # --- קבועי מחלקה ---
    DEFAULT_IP = "127.0.0.1"
    DEFAULT_PORT = 1729
    BACKLOG = 1                 # גודל תור החיבורים הממתינים; לקוח אחד בלבד בשלב זה
    TIME_FORMAT = "%H:%M:%S"

    # שמות הפקודות והתגובות
    PING = "PING"
    ECHO = "ECHO"
    TIME = "TIME"
    EXIT = "EXIT"
    ERROR = "ERROR"
    REPLY_PONG = "PONG"
    REPLY_BYE = "BYE"


    def __init__(self, ip: str = DEFAULT_IP, port: int = DEFAULT_PORT):
        """יוצר socket, מאפשר שימוש חוזר בכתובת, עושה bind ומתחיל להאזין ללקוח אחד."""

        self.__ip: str = ip
        self.__port: int = port
        self.__server: socket.socket = socket.socket()
        # מאפשר להריץ מחדש מיד אחרי סגירה, בלי "Address already in use" (מצב TIME_WAIT).
        # חייב להיקרא לפני bind.
        self.__server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.__server.bind((self.__ip, self.__port))
        self.__server.listen(NetworkServer.BACKLOG)


    def start(self) -> None:
        """ממתין ללקוח אחד (accept יחיד), מטפל בו, ובסוף סוגר את שקע השרת."""

        print(f"[SERVER] Listening on {self.__ip}:{self.__port}")

        try:
            client_socket, address = self.__server.accept()
            self.__handle_client(client_socket, address)

        except KeyboardInterrupt:
            print("[SERVER] Stopped by user")

        finally:
            self.__server.close()
            print("[SERVER] Server socket closed")


    def __handle_client(self, client_socket: socket.socket, address) -> None:
        """
        לולאת בקשה-תגובה מול לקוח אחד, עד EXIT או עד סיום החיבור.
        - הודעה לא תקינה (ProtocolError): המסגור תקין והזרם עדיין מסונכרן,
          לכן עונים ERROR וממשיכים לבקשה הבאה.
        - ניתוק (ConnectionError) או אורך חריג (ValueError): אי אפשר להתאושש
          (הלקוח נעלם, או שהגוף לא נקרא והזרם יצא מסנכרון), לכן מסיימים את החיבור.
        - EXIT: שולחים BYE ומסיימים.
        ה-socket של הלקוח נסגר בכל מקרה באמצעות with.
        """

        print(f"[SERVER] Client connected: {address}")

        with client_socket:
            try:
                while True:
                    try:
                        request = Protocol.receive(client_socket)

                    except ProtocolError as e:  # הזרם מסונכרן, אפשר להמשיך
                        Protocol.send(client_socket, ProtocolMessage(NetworkServer.ERROR, str(e)))
                        continue

                    Protocol.send(client_socket, self.__process(request))

                    if request.command == NetworkServer.EXIT:
                        break

            except (ConnectionError, ValueError) as e:  # ניתוק או הפרה שאין ממנה התאוששות
                print(f"[SERVER] Connection ended: {e}")


    def __process(self, msg: ProtocolMessage) -> ProtocolMessage:
        """מתרגם בקשה לתגובה. פקודה לא מוכרת -> הודעת ERROR."""

        command = msg.command

        if command == NetworkServer.PING:
            return ProtocolMessage(NetworkServer.PING, NetworkServer.REPLY_PONG)

        if command == NetworkServer.ECHO:
            return ProtocolMessage(NetworkServer.ECHO, msg.data)

        if command == NetworkServer.TIME:
            return ProtocolMessage(NetworkServer.TIME,
                                   datetime.now().strftime(NetworkServer.TIME_FORMAT))

        if command == NetworkServer.EXIT:
            return ProtocolMessage(NetworkServer.EXIT, NetworkServer.REPLY_BYE)

        return ProtocolMessage(NetworkServer.ERROR, f"Unknown command: {command}")


if __name__ == "__main__":
    NetworkServer().start()
