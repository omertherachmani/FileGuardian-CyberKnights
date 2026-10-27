import socket
from protocol import Protocol
from protocol_message import ProtocolMessage


class NetworkClient:

    DEFAULT_IP = "127.0.0.1"
    DEFAULT_PORT = 1729
    EXIT = "EXIT"


    def __init__(self, host = DEFAULT_IP, port = DEFAULT_PORT):
        self.__host = host
        self.__port = port
        self.__client_socket = socket.socket()

    def run(self):
        try:
            self.__client_socket.connect((self.__host, self.__port))

            while True:
                request = input("Enter command:\n>")
                protocol_request = ProtocolMessage.from_user_input(request)

                Protocol.send(self.__client_socket, protocol_request)
                server_msg = Protocol.receive(self.__client_socket)

                print(server_msg)

                if protocol_request.command == "EXIT":
                    break

        except ConnectionError as e:
            print(f"Client connection error: {e}")

        except Exception as e:
            print(f"Error: {e}")

        finally:
            self.__client_socket.close()

if __name__ == "__main__":
    client = NetworkClient('127.0.0.1', 1729)
    client.run()
