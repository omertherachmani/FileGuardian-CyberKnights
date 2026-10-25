import socket

class NetworkClient:

    def __init__(self,host='127.0.0.1',port = 0000):
        self.__host = host
        self.__port = port
        self.__client_socket = socket.socket()
        self.__protocol = 0

    def run(self):
        self.__client_socket.connect((self.__host,self.__port))
        self.__client_socket.recv(1024)
        client_msg = input("Enter command:\n>")

        while client_msg != "EXIT":
            self.__client_socket.send(client_msg.encode())
            server_msg = self.__client_socket.recv(1024).decode()
            print(server_msg)
            client_msg = input("Enter command:\n>")

        print("client disconected")
        self.__client_socket.close()