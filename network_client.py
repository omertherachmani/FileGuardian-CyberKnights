import socket
from Protocol import Protocol
from Protocol_Message import ProtocolMessage


class NetworkClient:

    def __init__(self, host='127.0.0.1', port=0000):
        self.__host = host
        self.__port = port
        self.__client_socket = socket.socket()

    def run(self):

        self.__client_socket.connect((self.__host, self.__port))

        while True:
            client_msg = input("Enter command:\n>")
            protocol_msg = ProtocolMessage.parse_user_input(client_msg)

            Protocol.send(self.__client_socket, protocol_msg)
            server_msg = Protocol.receive(self.__client_socket)
            print(server_msg)

            if protocol_msg.command == "EXIT":
                break

        self.__client_socket.close()
        print("client disconnected")

if __name__ == "__main__":
    client = NetworkClient('127.0.0.1', 1729)
    client.run()
