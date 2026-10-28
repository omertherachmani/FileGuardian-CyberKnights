import socket
import threading
import time
from datetime import datetime

import pytest

from network_client import NetworkClient
from network_server import NetworkServer
from protocol import Protocol
from protocol_message import ProtocolMessage


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


def test_1_ping():
    """
    בדיקת הפקודה PING.
    מוודא שהשרת עונה לבקשת PING בתשובה PONG.
    """
    start_server(5001)
    sock = connect(5001)

    Protocol.send(sock, ProtocolMessage("PING"))
    response = Protocol.receive(sock)

    assert response.data == "PONG", \
        f"Error in PING response: Expected 'PONG', " \
        f"got '{response.data}'"
    sock.close()

    print("✓ Test 1: PING returns PONG passed")


def test_2_echo_hebrew():
    """
    בדיקת הפקודה ECHO עם טקסט בעברית.
    מוודא שהשרת מחזיר בדיוק את אותו טקסט שקיבל, כולל תווים בעברית (UTF-8).
    """
    start_server(5002)
    sock = connect(5002)

    Protocol.send(sock, ProtocolMessage("ECHO", "שלום עולם"))
    response = Protocol.receive(sock)

    assert response.data == "שלום עולם", \
        f"Error in ECHO response: Expected 'שלום עולם', " \
        f"got '{response.data}'"
    sock.close()

    print("✓ Test 2: ECHO with Hebrew text passed")


def test_3_time():
    """
    בדיקת הפקודה TIME.
    מוודא שהשרת מחזיר שעה תקפה בפורמט HH:MM:SS.
    """
    start_server(5003)
    sock = connect(5003)

    Protocol.send(sock, ProtocolMessage("TIME"))
    response = Protocol.receive(sock)

    try:
        datetime.strptime(response.data, "%H:%M:%S")
    except ValueError:
        pytest.fail(
            f"Error in TIME response: Expected format HH:MM:SS, "
            f"got '{response.data}'"
        )
    sock.close()

    print("✓ Test 3: TIME returns a valid time passed")


def test_4_unknown_command():
    """
    בדיקת פקודה לא מוכרת.
    מוודא שהשרת עונה ERROR לפקודה שהוא לא מזהה.
    """
    start_server(5004)
    sock = connect(5004)

    Protocol.send(sock, ProtocolMessage("HELLO"))
    response = Protocol.receive(sock)

    assert response.command == "ERROR", \
        f"Error in unknown command response: Expected command 'ERROR', " \
        f"got '{response.command}'"
    sock.close()

    print("✓ Test 4: Unknown command returns ERROR passed")


def test_5_exit():
    """
    בדיקת הפקודה EXIT.
    מוודא שהשרת עונה BYE ואז סוגר את החיבור,
    כך שכל קריאה נוספת זורקת ConnectionError.
    """
    start_server(5005)
    sock = connect(5005)

    Protocol.send(sock, ProtocolMessage("EXIT"))
    response = Protocol.receive(sock)

    assert response.data == "BYE", \
        f"Error in EXIT response: Expected 'BYE', " \
        f"got '{response.data}'"

    # The server closed the connection, so another read raises ConnectionError
    with pytest.raises(ConnectionError):
        Protocol.receive(sock)
    sock.close()

    print("✓ Test 5: EXIT returns BYE and closes the connection passed")


def test_6_server_is_off():
    """
    בדיקת התחברות כשהשרת כבוי.
    מוודא שהלקוח זורק ConnectionError ולא קורס.
    לא מפעילים שרת על פורט 5006, ולכן אין עם מי להתחבר.
    """
    with pytest.raises(ConnectionError):
        NetworkClient("127.0.0.1", 5006).run()

    print("✓ Test 6: Connecting to a stopped server raises ConnectionError passed")


def test_7_two_requests():
    """
    בדיקת שתי בקשות רצופות על אותו חיבור.
    מוודא שהשרת מחזיר תשובה תקינה לכל אחת מהן.
    """
    start_server(5007)
    sock = connect(5007)

    Protocol.send(sock, ProtocolMessage("PING"))
    first = Protocol.receive(sock)

    Protocol.send(sock, ProtocolMessage("ECHO", "Hi"))
    second = Protocol.receive(sock)

    assert first.data == "PONG", \
        f"Error in first response: Expected 'PONG', " \
        f"got '{first.data}'"
    assert second.data == "Hi", \
        f"Error in second response: Expected 'Hi', " \
        f"got '{second.data}'"
    sock.close()

    print("✓ Test 7: Two consecutive requests passed")


def test_8_split_message():
    """
    בדיקת הודעה שמגיעה בחתיכות קטנות.
    מוודא שהשרת עדיין קורא אותה כהודעה אחת שלמה,
    גם כשהיא נשלחת 3 בתים בכל פעם עם השהיה בין החתיכות.
    """
    start_server(5008)
    sock = connect(5008)

    body = ProtocolMessage("ECHO", "Hello World").to_bytes()
    header = len(body).to_bytes(4, byteorder="big")
    all_bytes = header + body

    for i in range(0, len(all_bytes), 3):
        sock.sendall(all_bytes[i:i + 3])
        time.sleep(0.05)

    response = Protocol.receive(sock)

    assert response.data == "Hello World", \
        f"Error in split message handling: Expected 'Hello World', " \
        f"got '{response.data}'"
    sock.close()

    print("✓ Test 8: Split message is read as one message passed")


def test_9_echo_english():
    """
    בדיקת הפקודה ECHO עם טקסט באנגלית.
    מוודא שהשרת מחזיר בדיוק את אותו טקסט שקיבל (בדיקה משלימה לבדיקה 2).
    """
    start_server(5009)
    sock = connect(5009)

    Protocol.send(sock, ProtocolMessage("ECHO", "Hello World"))
    response = Protocol.receive(sock)

    assert response.data == "Hello World", \
        f"Error in ECHO response: Expected 'Hello World', " \
        f"got '{response.data}'"
    sock.close()

    print("✓ Test 9: ECHO with English text passed")