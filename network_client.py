import socket
from protocol import Protocol
from protocol_message import ProtocolMessage

class NetworkClient:

    #קבועים
    DEFAULT_IP = "127.0.0.1"
    DEFAULT_PORT = 1729
    EXIT = "EXIT"


    def __init__(self, host = DEFAULT_IP, port = DEFAULT_PORT):
        """פעולה בונה למחלקה: שומר את כתובת השרת והפורט ויוצר socket"""

        self.__host = host
        self.__port = port
        self.__client_socket = socket.socket()

    def run(self):
        """
        מנהל את התקשורת מול השרת בלולאה עד שהלקוח שולח EXIT.
        הלקוח שולח פקודה לשרת, הופך אותה להודעת פרוטוקול, שולח ומציג את תגובות השרת.
        כשהחיבור מתנתק (המשתמש מאזין EXIT) אז הסוקט של הלקוח נסגר לבסוף
        """
        try:
            #הלקוח מנסה להתחבר לשרת
            self.__client_socket.connect((self.__host, self.__port))


            while True:

                request = input("Enter command:\n>")

                #הופכים את ההודעה לאובייקט מסוג ProtocolMessage
                protocol_request = ProtocolMessage.from_user_input(request)

                #שליחת ההודעה המקודדת דרך הsocket לשרת
                Protocol.send(self.__client_socket, protocol_request)

                #קבלת הודעת תשובה מהשרת ופענוח בעזרת המחלקה Protocol
                server_msg = Protocol.receive(self.__client_socket)

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
            self.__client_socket.close()

if __name__ == "__main__":
    client = NetworkClient()
    client.run()
