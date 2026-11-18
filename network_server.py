import socket
import threading

from client_handler import ClientHandler


class NetworkServer:
    """
    שרת TCP שמקבל כמה לקוחות במקביל.

    לכל לקוח שמתחבר נוצר ClientHandler (Thread נפרד) שמטפל רק בו.
    השרת שומר רשימה של כל ה-handlers הפעילים, ורשימה זו מוגנת ב-Lock
    כי כמה threads ניגשים אליה באותו זמן.
    """


    DEFAULT_IP = "127.0.0.1"
    DEFAULT_PORT = 8000
    BACKLOG = 5          # כמה חיבורים יכולים לחכות בתור ל-accept
    JOIN_TIMEOUT = 2     # כמה שניות מחכים לכל handler בזמן סגירה


    def __init__(self, ip: str = DEFAULT_IP, port: int = DEFAULT_PORT) -> None:
        """
        יוצר את שקע ההאזנה ומתחיל להאזין (עדיין לא מקבל לקוחות).

        :param ip: כתובת ההאזנה (ברירת מחדל 127.0.0.1)
        :param port: הפורט להאזנה (ברירת מחדל 8000)
        :raises OSError: אם הפורט תפוס או שהכתובת אינה תקינה
        """

        self.__handlers = []
        self.__lock = threading.Lock()

        self.__server = socket.socket()
        # מאפשר להפעיל מחדש את השרת על אותו פורט מיד אחרי סגירה
        self.__server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.__server.bind((ip, port))
        self.__server.listen(self.BACKLOG)


    def start(self) -> None:
        """
        לולאת ה-accept הראשית: מקבלת לקוחות ויוצרת handler לכל אחד.

        רצה עד שיש שגיאה או עד CTRL + C, ואז סוגרת הכל דרך __shutdown.
        """

        ip, port = self.__server.getsockname()
        print(f"- Server: Listening on {ip}:{port}")

        try:
            while True:
                client_socket, address = self.__server.accept()
                handler = ClientHandler(client_socket, address, self)

                # רושמים את ה-handler לפני start כדי ש-CLIENTS יספור אותו נכון
                with self.__lock:
                    self.__handlers.append(handler)

                try:
                    handler.start()

                except RuntimeError as e:
                    # ה-Thread לא הופעל (למשל אין משאבים ליצירת Thread חדש).
                    # ה-handler לא ירוץ ולכן גם לא יסיר את עצמו, וה-socket לא ייסגר
                    # על ידו, אז השרת מנקה בעצמו וממשיך לקבל לקוחות אחרים.
                    print(f"- Server: Could not start handler for {address[0]}:{address[1]} - {e}")
                    self.remove_handler(handler)
                    client_socket.close()

        except OSError as e:
            # בדרך כלל השקע נסגר בזמן ש-accept מחכה, אבל זו יכולה להיות גם
            # שגיאת מערכת אחרת, ולכן מדפיסים את הסיבה
            print(f"- Server: Stopped accepting connections - {e}")

        except KeyboardInterrupt:
            print("- Server: Stopped by user (CTRL + C)")

        except Exception as e:
            print(f"- Server: Error - {e}")

        finally:
            print("- Server: Shutting down")
            self.__shutdown()


    def remove_handler(self, handler: ClientHandler) -> None:
        """
        מסיר handler מהרשימה. ה-handler קורא לפונקציה הזו בסוף ה-run שלו.
        בטוחה לקריאה גם אם ה-handler כבר הוסר.

        :param handler: ה-ClientHandler להסרה
        """

        with self.__lock:
            if handler in self.__handlers:
                self.__handlers.remove(handler)


    def client_count(self) -> int:
        """
        :return: מספר ה-handlers הרשומים ברגע הקריאה
        """

        with self.__lock:
            return len(self.__handlers)


    def __shutdown(self) -> None:
        """
        סוגר את השרת: סוגר את שקע ההאזנה, עוצר את כל ה-handlers
        ומחכה שיסיימו.

        חשוב: stop ו-join קורים מחוץ ל-Lock, כי ה-handler צריך את אותו Lock
        כדי להסיר את עצמו (remove_handler), ואחרת יהיה deadlock.
        """

        try:
            self.__server.close()
            print("- Server: Socket closed")

        except OSError:
            print("- Server: Unable to close socket")

        except Exception as e:
            print(f"- Server: Error - {e}")

        # מעתיקים את הרשימה כדי לעבור עליה בלי להחזיק את ה-Lock
        with self.__lock:
            handlers_copy = self.__handlers.copy()

        # stop משחרר את ה-recv החסום של כל handler
        for handler in handlers_copy:
            handler.stop()

        # מחכים שכל handler יסיים (לכל היותר JOIN_TIMEOUT שניות לכל אחד)
        for handler in handlers_copy:
            handler.join(self.JOIN_TIMEOUT)
            if handler.is_alive():
                print(f"- Server: {handler.name} did not stop in time")

        with self.__lock:
            self.__handlers.clear()

        print("- Server: All handlers closed")


if __name__ == "__main__":
    NetworkServer().start()
