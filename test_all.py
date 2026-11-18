import socket
import threading
import time
from datetime import datetime

import pytest

from network_client import NetworkClient
from network_server import NetworkServer
from protocol import Protocol, ProtocolMessage, ProtocolError


def start_server(port):
    """
    מפעיל שרת ברקע על הפורט שקיבלנו.
    השרת רץ ב-thread מסוג daemon, ולכן הוא נעצר כשהבדיקות מסתיימות.
    """
    server = NetworkServer("127.0.0.1", port)
    threading.Thread(target=server.start, daemon=True).start()


def connect(port):
    """
    מתחבר לשרת על הפורט שקיבלנו.
    מחזיר את ה-socket המחובר (עם timeout של 5 שניות).
    """
    sock = socket.socket()
    sock.settimeout(5)
    sock.connect(("127.0.0.1", port))
    return sock
    
