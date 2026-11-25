import socket
from threading import Lock

import gradio as gr

from network_client import NetworkClient
from protocol import Protocol, ProtocolMessage, ProtocolError


class GradioClientUI:
    """
    ממשק Gradio רב-משתמשים ללקוח הרשת.

    כל session בדפדפן (לשונית) מקבל NetworkClient משלו, ולכן שתי לשוניות
    הן שני חיבורי TCP עצמאיים לשרת. המילון __clients ממפה בין מזהה ה-session
    (request.session_hash) ללקוח שלו, והוא מוגן ב-Lock כי כמה callbacks
    רצים במקביל.

    ההיסטוריה נשמרת ברכיב ה-Chatbot בפורמט של רשימת הודעות:
    [{"role": "user" / "assistant", "content": "..."}].
    כל callback מחזיר רשימה של עדכוני רכיבים, בסדר הרכיבים שמוגדר ב-__build
    (chatbot, status, ip, port, connect, disconnect, command, data, send).
    """


    DEFAULT_COMMAND = "ECHO"
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    STATUS_CONNECTED = "Connected to {}:{}"
    STATUS_DISCONNECTED = "Disconnected"


    def __init__(self, ip: str = NetworkClient.DEFAULT_IP, port: int = NetworkClient.DEFAULT_PORT) -> None:
        """
        שומר את כתובת ברירת המחדל, יוצר את מילון הלקוחות והמנעול ובונה את ה-UI.

        :param ip: כתובת השרת שתופיע כברירת מחדל בשדה
        :param port: הפורט שיופיע כברירת מחדל בשדה
        """

        self.__clients: dict = {}
        self.__lock = Lock()
        self.__default_ip = ip
        self.__default_port = port
        self.demo: gr.Blocks = self.__build()


    def launch(self, **kwargs) -> None:
        """
        מפעיל את ממשק Gradio.

        :param kwargs: הפרמטרים של Blocks.launch, למשל server_port=7860 או share=True
        """

        self.demo.launch(**kwargs)


    def __build(self) -> gr.Blocks:
        """
        בונה את רכיבי התצוגה ומחבר אליהם את ה-callbacks.

        :return: ממשק ה-Gradio המוכן
        """

        with gr.Blocks(title="Network Client") as demo:
            gr.Markdown("# Network Client")

            with gr.Row():
                ip_input = gr.Textbox(label="Server IP", value=self.__default_ip, scale=2)
                port_input = gr.Number(label="Port", value=self.__default_port, scale=1, precision=0)

            with gr.Row():
                connect_btn = gr.Button("Connect", variant="primary")
                disconnect_btn = gr.Button("Disconnect", variant="stop", interactive=False)

            status_box = gr.Textbox(label="Status", value=self.STATUS_DISCONNECTED, interactive=False)

            gr.Markdown("---")

            with gr.Row():
                command_dropdown = gr.Dropdown(label="Command", choices=Protocol.COMMANDS,
                                               value=self.DEFAULT_COMMAND, interactive=False)
                data_input = gr.Textbox(label="Data (if required)", interactive=False, scale=2,
                                        visible=self.DEFAULT_COMMAND in Protocol.COMMANDS_WITH_DATA)

            send_btn = gr.Button("Send", variant="secondary", interactive=False)

            gr.Markdown("### Requests and Replies History")
            chatbot = gr.Chatbot(label="Chat History", height=300)
            clear_btn = gr.Button("Clear log")

            # הסדר כאן חייב להתאים לסדר הרשימה ש-__view מחזירה
            outputs = [chatbot, status_box, ip_input, port_input, connect_btn,
                       disconnect_btn, command_dropdown, data_input, send_btn]

            # concurrency_limit=None: ברירת המחדל של Gradio מריצה callback אחד בכל פעם
            # לכל המשתמשים, ואז לקוח שממתין לתשובה מהשרת היה מעכב את הלקוחות האחרים
            connect_btn.click(self.__connect,
                              inputs=[ip_input, port_input, command_dropdown, chatbot],
                              outputs=outputs, concurrency_limit=None)

            disconnect_btn.click(self.__disconnect,
                                 inputs=[command_dropdown, chatbot],
                                 outputs=outputs, concurrency_limit=None)

            send_btn.click(self.__send,
                           inputs=[command_dropdown, data_input, chatbot],
                           outputs=outputs, concurrency_limit=None)

            command_dropdown.change(self.__on_command_change, inputs=command_dropdown, outputs=data_input)

            clear_btn.click(lambda: [], inputs=None, outputs=chatbot)

            # ניקוי חיבור כשהלשונית נסגרת או מתרעננת בלי לחיצה על Disconnect
            demo.unload(self.__on_unload)

        return demo


    def __get_client(self, request: gr.Request) -> NetworkClient:
        """
        מאתר את הלקוח של ה-session הנוכחי.

        :param request: בקשת Gradio (נותנת את מזהה ה-session)
        :return: ה-NetworkClient של ה-session, או None אם אין לו חיבור
        """

        with self.__lock:
            return self.__clients.get(request.session_hash)


    def __remove_client(self, request: gr.Request) -> None:
        """
        מסיר את הלקוח של ה-session מהמילון וסוגר אותו.
        ה-close מתבצע מחוץ ל-Lock כדי לא לחסום callbacks של sessions אחרים.
        בטוחה לקריאה גם אם אין ל-session לקוח.

        :param request: בקשת Gradio (נותנת את מזהה ה-session)
        """

        with self.__lock:
            client = self.__clients.pop(request.session_hash, None)

        if client is not None:
            client.close()


    def __on_unload(self, request: gr.Request) -> None:
        """
        נקרא כש-session מסתיים (סגירת לשונית או רענון): סוגר את החיבור שלו.

        :param request: בקשת Gradio (נותנת את מזהה ה-session)
        """

        self.__remove_client(request)


    def __view(self, history: list, client: NetworkClient, command: str, clear_data: bool) -> list:
        """
        בונה את עדכוני כל הרכיבים לפי מצב החיבור.

        :param history: היסטוריית ההודעות להצגה
        :param client: הלקוח של ה-session, או None אם אין חיבור
        :param command: הפקודה שנבחרה (קובעת אם שדה הנתונים מוצג)
        :param clear_data: האם לנקות את שדה הנתונים
        :return: רשימת עדכונים לפי סדר הרכיבים ב-__build
        """

        connected = client is not None and client.connected

        if connected:
            status = self.STATUS_CONNECTED.format(*client.address)
        else:
            status = self.STATUS_DISCONNECTED

        # שדה הנתונים מוצג רק לפקודות שדורשות נתונים, ומתנקה כשהוא מוסתר
        needs_data = command in Protocol.COMMANDS_WITH_DATA

        if needs_data and not clear_data:
            data_update = gr.update(visible=True, interactive=connected)
        else:
            data_update = gr.update(visible=needs_data, interactive=connected, value="")

        return [
            history,
            status,
            gr.update(interactive=not connected),  # ip_input
            gr.update(interactive=not connected),  # port_input
            gr.update(interactive=not connected),  # connect_btn
            gr.update(interactive=connected),      # disconnect_btn
            gr.update(interactive=connected),      # command_dropdown
            data_update,                           # data_input
            gr.update(interactive=connected),      # send_btn
        ]


    def __add(self, history: list, role: str, text: str) -> list:
        """
        מוסיף הודעה להיסטוריה.

        :param history: ההיסטוריה הקיימת (לא משתנה)
        :param role: ROLE_USER לבקשה או ROLE_ASSISTANT לתשובה והודעות מערכת
        :param text: תוכן ההודעה
        :return: היסטוריה חדשה עם ההודעה בסוף
        """

        return history + [{"role": role, "content": text}]


    @staticmethod
    def __describe(error: Exception) -> str:
        """
        ממיר חריגה להודעה מובנת למשתמש, בלי traceback.

        :param error: החריגה שנתפסה
        :return: טקסט קצר שמסביר מה קרה
        """

        if isinstance(error, (TimeoutError, socket.timeout)):
            return "Timed out waiting for the server. The connection was closed."

        if isinstance(error, ConnectionRefusedError):
            return "The server refused the connection. Is it running, and are the IP and port correct?"

        if isinstance(error, socket.gaierror):
            return "Could not resolve the server address."

        if isinstance(error, ConnectionError):
            return "The connection to the server was lost."

        if isinstance(error, ProtocolError):
            return f"The server sent an invalid reply ({error})."

        if isinstance(error, ValueError):
            return f"Invalid input: {error}"

        if isinstance(error, OSError):
            return f"Network error: {error.strerror or error}"

        return f"Unexpected error: {error}"


    def __connect(self, ip: str, port, command: str, history: list, request: gr.Request) -> list:
        """
        יוצר חיבור ל-session הנוכחי ומעדכן את התצוגה.
        שגיאות (כתובת ריקה, פורט לא תקין, שרת לא זמין) מוצגות בהיסטוריה.

        :param ip: כתובת השרת מהשדה
        :param port: הפורט מהשדה
        :param command: הפקודה שנבחרה
        :param history: היסטוריית ההודעות
        :param request: בקשת Gradio (נותנת את מזהה ה-session)
        :return: רשימת עדכוני רכיבים
        """

        history = history or []
        ip = (ip or "").strip()

        try:
            port_number = int(port)
            if not 1 <= port_number <= 65535:
                raise ValueError

        except (TypeError, ValueError):
            history = self.__add(history, self.ROLE_ASSISTANT,
                                 "Connection failed: the port must be a number between 1 and 65535.")
            return self.__view(history, self.__get_client(request), command, False)

        if not ip:
            history = self.__add(history, self.ROLE_ASSISTANT, "Connection failed: the server IP is empty.")
            return self.__view(history, self.__get_client(request), command, False)

        # אם כבר היה חיבור ל-session הזה, סוגרים אותו כדי לא להשאיר socket יתום
        self.__remove_client(request)

        try:
            # החיבור עצמו יכול להימשך עד CONNECT_TIMEOUT, ולכן קורה מחוץ ל-Lock
            client = NetworkClient(ip, port_number)

        except Exception as e:
            history = self.__add(history, self.ROLE_ASSISTANT, f"Connection failed: {self.__describe(e)}")
            return self.__view(history, None, command, False)

        with self.__lock:
            self.__clients[request.session_hash] = client

        history = self.__add(history, self.ROLE_ASSISTANT, f"Connected to {ip}:{port_number}")
        return self.__view(history, client, command, False)


    def __disconnect(self, command: str, history: list, request: gr.Request) -> list:
        """
        מנתק את ה-session הנוכחי: שולח EXIT לשרת (ניסיון בלבד) וסוגר את הלקוח.
        sessions אחרים לא מושפעים.

        :param command: הפקודה שנבחרה
        :param history: היסטוריית ההודעות
        :param request: בקשת Gradio (נותנת את מזהה ה-session)
        :return: רשימת עדכוני רכיבים
        """

        history = history or []
        client = self.__get_client(request)

        if client is not None and client.connected:
            try:
                client.request(ProtocolMessage(NetworkClient.EXIT))
            except Exception:
                pass  # מנתקים בכל מקרה, גם אם השרת לא ענה

        self.__remove_client(request)

        history = []
        return self.__view(history, None, command, True)


    def __send(self, command: str, data: str, history: list, request: gr.Request) -> list:
        """
        בונה ProtocolMessage, שולח אותו בחיבור של ה-session ומציג את התגובה.

        אחרי EXIT או שגיאת רשת (ניתוק, timeout, תשובה לא תקינה) החיבור כבר נסגר
        על ידי NetworkClient, ולכן ה-session מוסר והתצוגה חוזרת למצב מנותק.
        הודעה לא חוקית (ValueError) לא שולחת דבר, והחיבור נשאר פעיל.

        :param command: הפקודה שנבחרה
        :param data: הנתונים מהשדה (נשלחים רק לפקודות שדורשות נתונים)
        :param history: היסטוריית ההודעות
        :param request: בקשת Gradio (נותנת את מזהה ה-session)
        :return: רשימת עדכוני רכיבים
        """

        history = history or []
        client = self.__get_client(request)

        if client is None or not client.connected:
            self.__remove_client(request)
            history = self.__add(history, self.ROLE_ASSISTANT, "Not connected to a server.")
            return self.__view(history, None, command, False)

        message_data = data if (data and command in Protocol.COMMANDS_WITH_DATA) else ""
        request_text = f"{command} {message_data}" if message_data else command

        history = self.__add(history, self.ROLE_USER, request_text)

        try:
            response = client.request(ProtocolMessage(command, message_data))

        except ValueError as e:
            history = self.__add(history, self.ROLE_ASSISTANT, f"Error: {self.__describe(e)}")
            return self.__view(history, client, command, False)

        except Exception as e:
            history = self.__add(history, self.ROLE_ASSISTANT, f"Error: {self.__describe(e)}")
            self.__remove_client(request)
            return self.__view(history, None, command, False)

        if response.data:
            response_text = f"{response.command}: {response.data}"
        else:
            response_text = response.command

        history = self.__add(history, self.ROLE_ASSISTANT, response_text)

        # EXIT סוגר את החיבור, ואז מסירים את ה-session
        if not client.connected:
            self.__remove_client(request)

        return self.__view(history, client, command, False)


    def __on_command_change(self, command: str):
        """
        מעדכן את שדה הנתונים כשסוג הפקודה משתנה: מוצג רק לפקודות שדורשות נתונים,
        ומתנקה כשהוא מוסתר.

        :param command: הפקודה שנבחרה
        :return: עדכון לשדה הנתונים
        """

        if command in Protocol.COMMANDS_WITH_DATA:
            return gr.update(visible=True)

        return gr.update(visible=False, value="")


def main() -> None:
    """נקודת הכניסה: מפעיל את ממשק ה-Gradio מקומית (בלי קישור ציבורי)."""

    GradioClientUI().launch()


if __name__ == "__main__":
    main()
