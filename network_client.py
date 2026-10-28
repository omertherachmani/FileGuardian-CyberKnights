import socket

from protocol import Protocol
from protocol_error import ProtocolError
from protocol_message import ProtocolMessage


class NetworkClient:
    """
    צד הלקוח: מתחבר לשרת, קורא פקודות מהמשתמש, שולח אותן ומציג את התגובות.
    הלקוח אחראי רק על הקלט והפלט; הקידוד והמסגור נמצאים ב-ProtocolMessage וב-Protocol.
    """

    # --- קבועי מחלקה ---
    __DEFAULT_IP = "127.0.0.1"
    __DEFAULT_PORT = 1729
    __EXIT = "EXIT"


    def __init__(self, ip: str = __DEFAULT_IP, port: int = __DEFAULT_PORT):
        """
        יוצר socket ומתחבר מיד לשרת.
        אם ההתחברות נכשלה (למשל השרת כבוי) סוגר את ה-socket ומעלה ConnectionError.
        """

        self.__sock: socket.socket = socket.socket()

        try:
            self.__sock.connect((ip, port))

        except OSError as e:
            self.__sock.close()
            raise ConnectionError(f"Could not connect to {ip}:{port} ({e})") from e


    def run(self) -> None:
        """
        לולאת קלט: הופכת טקסט להודעה, שולחת אותה, מקבלת תגובה ומציגה אותה.
        מסתיימת אחרי __EXIT או כשהחיבור נקטע; קלט ריק מדווח וממשיך.
        ה-socket נסגר בכל מקרה.
        """

        try:
            while True:
                line = input("Enter command:\n>")

                try:
                    request = ProtocolMessage.from_user_input(line)
                except ValueError as e:  # למשל קלט ריק
                    print(f"[CLIENT] Invalid input: {e}")
                    continue

                Protocol.send(self.__sock, request)
                response = Protocol.receive(self.__sock)
                print(response)

                if request.command == NetworkClient.__EXIT:
                    break

        except (ConnectionError, ProtocolError, ValueError) as e:
            print(f"[CLIENT] Connection ended: {e}")

        except (KeyboardInterrupt, EOFError):
            print("\n[CLIENT] Stopped by user")

        finally:
            self.__sock.close()
            print("[CLIENT] Client disconnected")


if __name__ == "__main__":
    try:
        NetworkClient().run()

    except ConnectionError as e:
        print(f"[CLIENT] {e}")
