"""
בדיקות קבלה - שלב 8 (דף עבודה 2): כל 15 הבדיקות בקובץ אחד.

כל בדיקה מפעילה שרת משלה על פורט משלו (5001-5015), ולכן הבדיקות לא תלויות זו בזו.
בדיקות 10-13 בודקות את ממשק ה-Gradio, ואם Gradio לא מותקן הן מדולגות.

התקנה (פעם אחת):   pip install pytest
הרצה:              python test_all.py
או:                python -m pytest test_all.py -v -s
"""

import socket
import threading
import time

import pytest

from network_server import NetworkServer
from protocol import Protocol, ProtocolMessage

try:
    import GradioClientUI
except ImportError:  # Gradio לא מותקן
    UI = None


HOST = "127.0.0.1"

# מיקומי הרכיבים ברשימה ש-callbacks של ה-UI מחזירים
CHAT, STATUS = 0, 1


# --- פעולות עזר ---

def start_server(port):
    """מפעיל שרת ב-Thread ברקע ומחזיר אותו."""

    server = NetworkServer(HOST, port)
    thread = threading.Thread(target=server.start, daemon=True)
    thread.start()
    server.thread = thread
    return server


def stop_server(server, port):
    """
    עוצר שרת ומחכה שיסיים את הסגירה.

    לשרת אין פעולת עצירה ציבורית, ו-accept חסום לא מתעורר כשסוגרים את השקע
    מ-Thread אחר. לכן סוגרים את שקע ההאזנה ומתחברים פעם אחת כדי להעיר את
    ה-accept, והשרת עובר ל-__shutdown הרגיל (כמו ב-CTRL + C).
    """

    server._NetworkServer__server.close()

    try:
        socket.create_connection((HOST, port), timeout=1).close()
    except OSError:
        pass

    server.thread.join(10)


def connect(port):
    """פותח חיבור TCP לשרת ומחזיר את ה-socket."""

    return socket.create_connection((HOST, port), timeout=5)


def send_raw(sock, body):
    """שולח גוף הודעה עם כותרת אורך תקינה (לבדיקות של הודעות פגומות)."""

    header = len(body).to_bytes(Protocol.HEADER_SIZE, Protocol.BYTE_ORDER)
    sock.sendall(header + body)


class FakeRequest:
    """בקשת Gradio מדומה: ה-UI משתמש רק במזהה ה-session."""

    def __init__(self, session_hash):
        self.session_hash = session_hash


def ui_call(ui, name, *args):
    """קורא לפעולה הפרטית של ה-UI לפי שמה (בלי הקידומת __)."""

    return getattr(ui, "_GradioClientUI__" + name)(*args)


def field(update, name):
    """קורא שדה מעדכון רכיב של Gradio (מילון או אובייקט, לפי הגרסה)."""

    if isinstance(update, dict):
        return update[name]
    return getattr(update, name)


# --- בדיקות 1-9: שרת ופרוטוקול ---

def test_1_three_clients_ping():
    """
    שלושה לקוחות מסוף מתחברים ושולחים PING.
    מוודא ששלושה חיבורים מתקבלים במקביל (גם כשהקודמים ממתינים לקלט)
    ושכל לקוח מקבל PONG.
    """

    start_server(5001)
    socks = [connect(5001) for _ in range(3)]

    for sock in socks:
        Protocol.send(sock, ProtocolMessage("PING"))

    for number, sock in enumerate(socks, start=1):
        response = Protocol.receive(sock)

        assert response.data == "PONG", \
            f"Error in PING response of client {number}: Expected 'PONG', " \
            f"got '{response.data}'"
        sock.close()

    print("✓ Test 1: three clients receive PONG passed")


def test_2_two_clients_time_echo():
    """
    שני לקוחות שולחים TIME ו-ECHO במקביל.
    מוודא שכל לקוח מקבל את התגובה המתאימה לבקשה שלו.
    """

    start_server(5002)
    sock_a = connect(5002)
    sock_b = connect(5002)

    # שתי הבקשות נשלחות לפני שמישהו קורא תשובה, כלומר שתיהן בפעולה באותו זמן
    Protocol.send(sock_a, ProtocolMessage("TIME"))
    Protocol.send(sock_b, ProtocolMessage("ECHO", "שלום עולם"))
    response_a = Protocol.receive(sock_a)
    response_b = Protocol.receive(sock_b)

    assert response_a.command == "TIME" and len(response_a.data) == len("HH:MM:SS"), \
        f"Error in TIME response: Expected a time like 'HH:MM:SS', " \
        f"got '{response_a}'"
    assert response_b.command == "ECHO" and response_b.data == "שלום עולם", \
        f"Error in ECHO response: Expected 'ECHO|שלום עולם', " \
        f"got '{response_b}'"
    sock_a.close()
    sock_b.close()

    print("✓ Test 2: TIME and ECHO in parallel passed")


def test_3_clients_count_three():
    """
    CLIENTS בשלושה חיבורים.
    מוודא שהשרת מחזיר CLIENTS|3 כשיש שלושה לקוחות מחוברים.
    """

    start_server(5003)
    socks = [connect(5003) for _ in range(3)]

    # PING מכל לקוח מוכיח שה-handler שלו כבר רשום ורץ
    for sock in socks:
        Protocol.send(sock, ProtocolMessage("PING"))
        Protocol.receive(sock)

    Protocol.send(socks[0], ProtocolMessage("CLIENTS"))
    response = Protocol.receive(socks[0])

    assert str(response) == "CLIENTS|3", \
        f"Error in CLIENTS response: Expected 'CLIENTS|3', " \
        f"got '{response}'"
    for sock in socks:
        sock.close()

    print("✓ Test 3: CLIENTS returns 3 passed")


def test_4_exit_one_client():
    """
    EXIT של לקוח יחיד.
    מוודא שהלקוח מקבל BYE ומתנתק, ושלקוח אחר ממשיך לקבל שירות.
    """

    start_server(5004)
    leaving = connect(5004)
    staying = connect(5004)

    Protocol.send(leaving, ProtocolMessage("EXIT"))
    response = Protocol.receive(leaving)

    assert response.data == "BYE", \
        f"Error in EXIT response: Expected 'BYE', " \
        f"got '{response.data}'"
    assert Protocol.receive(leaving) is None, \
        "Error: the server did not close the connection after EXIT"

    Protocol.send(staying, ProtocolMessage("PING"))
    response = Protocol.receive(staying)

    assert response.data == "PONG", \
        f"Error: the other client stopped working after EXIT: " \
        f"Expected 'PONG', got '{response.data}'"
    leaving.close()
    staying.close()

    print("✓ Test 4: EXIT disconnects only that client passed")


def test_5_clients_after_removal():
    """
    CLIENTS לאחר הסרת handler.
    מוודא שהמספר קטן באחד אחרי שלקוח שולח EXIT.
    """

    start_server(5005)
    socks = [connect(5005) for _ in range(3)]

    for sock in socks:
        Protocol.send(sock, ProtocolMessage("PING"))
        Protocol.receive(sock)

    Protocol.send(socks[2], ProtocolMessage("EXIT"))
    Protocol.receive(socks[2])
    time.sleep(0.3)  # נותנים ל-handler להסיר את עצמו מהרשימה

    Protocol.send(socks[0], ProtocolMessage("CLIENTS"))
    response = Protocol.receive(socks[0])

    assert response.data == "2", \
        f"Error in CLIENTS after EXIT: Expected '2', " \
        f"got '{response.data}'"
    for sock in socks:
        sock.close()

    print("✓ Test 5: CLIENTS decreases by one passed")


def test_6_abrupt_disconnect():
    """
    ניתוק פתאומי של לקוח.
    מוודא שהשרת לא קורס כשלקוח נסגר באמצע שליחת הודעה,
    ושלקוח אחר ממשיך לעבוד.
    """

    server = start_server(5006)
    good = connect(5006)
    Protocol.send(good, ProtocolMessage("PING"))
    Protocol.receive(good)

    bad = connect(5006)
    bad.sendall(b"\x00\x00\x00\x10AB")  # כותרת של 16 בתים, אבל נשלחו רק 2
    bad.close()
    time.sleep(0.3)

    Protocol.send(good, ProtocolMessage("PING"))
    response = Protocol.receive(good)

    assert response.data == "PONG", \
        f"Error: server stopped working after abrupt disconnect: " \
        f"Expected 'PONG', got '{response.data}'"
    assert server.client_count() == 1, \
        f"Error: the disconnected client was not removed: " \
        f"Expected 1 client, got {server.client_count()}"
    good.close()

    print("✓ Test 6: abrupt disconnect does not crash the server passed")


def test_7_unknown_command():
    """
    פקודה לא מוכרת.
    מוודא שהשרת מחזיר ERROR ושהחיבור נשאר פתוח.
    """

    start_server(5007)
    sock = connect(5007)

    Protocol.send(sock, ProtocolMessage("FOO"))
    response = Protocol.receive(sock)

    assert response.command == "ERROR" and "FOO" in response.data, \
        f"Error in unknown command response: Expected 'ERROR' mentioning 'FOO', " \
        f"got '{response}'"

    Protocol.send(sock, ProtocolMessage("PING"))
    response = Protocol.receive(sock)

    assert response.data == "PONG", \
        f"Error: connection stopped working after ERROR: " \
        f"Expected 'PONG', got '{response.data}'"
    sock.close()

    print("✓ Test 7: unknown command returns ERROR passed")


def test_8_fragmented_message():
    """
    הודעה מפוצלת ב-TCP.
    מוודא שהשרת מרכיב הודעה שהגיעה בחלקים קטנים (3 בתים בכל פעם)
    ומחזיר אותה שלמה.
    """

    start_server(5008)
    sock = connect(5008)

    body = ProtocolMessage("ECHO", "פיצול").to_bytes()
    message = len(body).to_bytes(Protocol.HEADER_SIZE, Protocol.BYTE_ORDER) + body

    for i in range(0, len(message), 3):
        sock.sendall(message[i:i + 3])
        time.sleep(0.01)

    response = Protocol.receive(sock)

    assert response.data == "פיצול", \
        f"Error in fragmented ECHO: Expected 'פיצול', " \
        f"got '{response.data}'"
    sock.close()

    print("✓ Test 8: fragmented message decoded passed")


def test_9_invalid_message():
    """
    הודעה לא תקינה.
    מוודא שהודעה בלי מפריד והודעה עם UTF-8 פגום מקבלות ERROR
    (ProtocolError מטופל בשרת), ושהחיבור נשאר תקין אחריהן.
    """

    start_server(5009)
    sock = connect(5009)

    send_raw(sock, b"abc")  # אין מפריד
    response = Protocol.receive(sock)

    assert response.command == "ERROR", \
        f"Error in message without separator: Expected 'ERROR', " \
        f"got '{response}'"

    send_raw(sock, b"\xff\xfe")  # UTF-8 לא תקין
    response = Protocol.receive(sock)

    assert response.command == "ERROR", \
        f"Error in invalid UTF-8 message: Expected 'ERROR', " \
        f"got '{response}'"

    Protocol.send(sock, ProtocolMessage("PING"))
    response = Protocol.receive(sock)

    assert response.data == "PONG", \
        f"Error: connection stopped working after invalid messages: " \
        f"Expected 'PONG', got '{response.data}'"
    sock.close()

    print("✓ Test 9: invalid message handled passed")


# --- בדיקות 10-13: --- Gradio

def test_10_gradio_two_sessions():
    """
    Gradio: שני sessions נפרדים.
    מוודא ששני sessions יוצרים שני חיבורים עצמאיים לשרת.
    """

    if UI is None:
        pytest.skip("Gradio is not installed")

    server = start_server(5010)
    ui = UI.GradioClientUI(HOST, 5010)
    request_a = FakeRequest("tab-A")
    request_b = FakeRequest("tab-B")

    out_a = ui_call(ui, "connect", HOST, 5010, "PING", [], request_a)
    out_b = ui_call(ui, "connect", HOST, 5010, "PING", [], request_b)
    time.sleep(0.3)

    client_a = ui_call(ui, "get_client", request_a)
    client_b = ui_call(ui, "get_client", request_b)

    assert out_a[STATUS].startswith("Connected") and out_b[STATUS].startswith("Connected"), \
        f"Error in Gradio connect: Expected both sessions 'Connected', " \
        f"got '{out_a[STATUS]}' and '{out_b[STATUS]}'"
    assert client_a is not client_b, \
        "Error: the two sessions share the same client"
    assert server.client_count() == 2, \
        f"Error: Expected 2 connections on the server, " \
        f"got {server.client_count()}"

    ui_call(ui, "on_unload", request_a)
    ui_call(ui, "on_unload", request_b)

    print("✓ Test 10: Gradio sessions have independent connections passed")


def test_11_gradio_disconnect_one_session():
    """
    Gradio: ניתוק session אחד.
    מוודא שה-session השני ממשיך לעבוד.
    """

    if UI is None:
        pytest.skip("Gradio is not installed")

    start_server(5011)
    ui = UI.GradioClientUI(HOST, 5011)
    request_a = FakeRequest("tab-A")
    request_b = FakeRequest("tab-B")

    ui_call(ui, "connect", HOST, 5011, "PING", [], request_a)
    ui_call(ui, "connect", HOST, 5011, "PING", [], request_b)
    time.sleep(0.3)

    out_a = ui_call(ui, "disconnect", "PING", [], request_a)
    time.sleep(0.3)

    assert out_a[STATUS] == "Disconnected", \
        f"Error in Gradio disconnect: Expected 'Disconnected', " \
        f"got '{out_a[STATUS]}'"

    out_b = ui_call(ui, "send", "CLIENTS", "", [], request_b)
    reply = out_b[CHAT][-1]["content"]

    assert reply == "CLIENTS: 1", \
        f"Error: the other session stopped working: Expected 'CLIENTS: 1', " \
        f"got '{reply}'"

    ui_call(ui, "on_unload", request_b)

    print("✓ Test 11: Gradio disconnect keeps the other session passed")


def test_12_gradio_command_change():
    """
    Gradio: שינוי פקודה.
    מוודא ששדה הנתונים מוצג רק לפקודות שדורשות נתונים, ומתנקה כשהוא מוסתר.
    """

    if UI is None:
        pytest.skip("Gradio is not installed")

    ui = UI.GradioClientUI(HOST, 5012)

    for command in Protocol.COMMANDS:
        update = ui_call(ui, "on_command_change", command)
        expected = command in Protocol.COMMANDS_WITH_DATA

        assert field(update, "visible") == expected, \
            f"Error in data field of {command}: Expected visible={expected}, " \
            f"got visible={field(update, 'visible')}"

        if not expected:
            assert field(update, "value") == "", \
                f"Error: the hidden data field of {command} was not cleared"

    print("✓ Test 12: Gradio data field matches the command passed")


def test_13_gradio_connection_error():
    """
    Gradio: שגיאת חיבור.
    מוודא שהתחברות לפורט שאין עליו שרת מציגה הודעת שגיאה מובנת (בלי traceback)
    והממשק נשאר במצב מנותק.
    """

    if UI is None:
        pytest.skip("Gradio is not installed")

    ui = UI.GradioClientUI(HOST, 5013)

    out = ui_call(ui, "connect", HOST, 5013, "PING", [], FakeRequest("tab-A"))  # אין שרת בפורט הזה
    message = out[CHAT][-1]["content"]

    assert message.startswith("Connection failed:"), \
        f"Error in connection error message: Expected it to start with " \
        f"'Connection failed:', got '{message}'"
    assert "Traceback" not in message, \
        f"Error: the message shows a traceback: '{message}'"
    assert out[STATUS] == "Disconnected", \
        f"Error: Expected status 'Disconnected', " \
        f"got '{out[STATUS]}'"

    print("✓ Test 13: Gradio shows a readable connection error passed")


# ------------------------------------------------------- בדיקות 14-15: סגירה והפעלה מחדש

def test_14_shutdown_with_active_clients():
    """
    עצירת שרת עם לקוחות פעילים.
    מוודא שהשרת מסיים, מסיר את כל ה-handlers וסוגר את חיבורי הלקוחות.
    """

    server = start_server(5014)
    socks = [connect(5014) for _ in range(3)]

    for sock in socks:
        Protocol.send(sock, ProtocolMessage("PING"))
        Protocol.receive(sock)

    stop_server(server, 5014)

    assert not server.thread.is_alive(), \
        "Error: the server did not finish shutting down"
    assert server.client_count() == 0, \
        f"Error: handlers were not removed: Expected 0, " \
        f"got {server.client_count()}"

    for sock in socks:
        try:
            Protocol.send(sock, ProtocolMessage("PING"))
            response = Protocol.receive(sock)
        except OSError:
            response = None

        assert response is None, \
            f"Error: a client connection stayed open after shutdown: got '{response}'"
        sock.close()

    print("✓ Test 14: shutdown with active clients passed")


def test_15_restart_same_port():
    """
    הפעלה מחדש על אותו port.
    מוודא שאפשר להפעיל שרת חדש מיד אחרי שהקודם נסגר, והוא עונה ללקוחות.
    """

    server = start_server(5015)

    # PING מוכיח שהשרת כבר רץ לפני שעוצרים אותו
    sock = connect(5015)
    Protocol.send(sock, ProtocolMessage("PING"))
    Protocol.receive(sock)
    sock.close()

    stop_server(server, 5015)

    start_server(5015)  # אם הפורט תפוס, כאן תיזרק OSError
    sock = connect(5015)

    Protocol.send(sock, ProtocolMessage("PING"))
    response = Protocol.receive(sock)

    assert response.data == "PONG", \
        f"Error in PING after restart: Expected 'PONG', " \
        f"got '{response.data}'"
    sock.close()

    print("✓ Test 15: restart on the same port passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
