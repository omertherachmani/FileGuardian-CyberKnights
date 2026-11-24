import gradio as gr
from network_client import NetworkClient
from protocol import ProtocolMessage

with gr.Blocks() as demo:
    # State לשמירת מופע ה-NetworkClient של המשתמש הנוכחי
    client_state = gr.State(None)

    gr.Markdown("#Network Client")

    with gr.Row():
        ip_input = gr.Textbox(label="Server IP", value=NetworkClient.DEFAULT_IP, scale=2)
        port_input = gr.Number(label="Port", value=NetworkClient.DEFAULT_PORT, scale=1, precision=0)

    with gr.Row():
        connect_btn = gr.Button("Connect", variant="primary")
        disconnect_btn = gr.Button("Disconnect", variant="stop", interactive=False)

    status_box = gr.Textbox(label="Status", value="Disconnected", interactive=False)

    gr.Markdown("---")

    with gr.Row():
        command_dropdown = gr.Dropdown(label="Command", choices=["PING", "ECHO", "TIME", "EXIT", "CLIENTS"] ,value="ECHO", interactive=False)
        data_input = gr.Textbox(label="Data (if required)", interactive=False, scale=2)

    send_btn = gr.Button("Send", variant="secondary", interactive=False)

    gr.Markdown("### Requests and Replies History")
    chatbot = gr.Chatbot(label="Chat History", height=300)
    clear_btn = gr.Button("Clear log")


    # --- פונקציות לוגיקה וחיבור ---

    def visible_data(data):
        if data == "ECHO":
            return gr.update(visible = True)
        return gr.update(visible=False, value = "")

    def connect_to_server(ip, port, history):
        try:
            client = NetworkClient(ip, int(port))
            status_msg = f"Connected to {ip}: {port}"

            history = history + [ {"role": "assistant", "content": "[info]" + status_msg} ]
            return (
                client,
                status_msg,
                gr.update(interactive=False), # ip_input
                gr.update(interactive=False), # port_input
                gr.update(interactive=False),  # connect_btn
                gr.update(interactive=True),  # disconnect_btn
                gr.update(interactive=True),  # command_dropdown
                gr.update(interactive=True),  # data_input
                gr.update(interactive=True),  # send_btn
                history
            )
        except Exception as e:
            history = history + [ {"role": "assistant", "content": f"Connection failed: {e}"} ]
            return (
                None,
                f"Connection failed: {e}",
                gr.update(interactive=True),
                gr.update(interactive=True),
                gr.update(interactive=True),
                gr.update(interactive=False),
                gr.update(interactive=False),
                gr.update(interactive=False),
                gr.update(interactive=False),
                history
            )


    def disconnect_from_server(client):
        if client:
            try:
                if client.connected:
                    try:
                        client.request(ProtocolMessage("EXIT", "BYE"))
                    except Exception:
                        pass
                client.close()
            except Exception:
                pass

        return (
            None,
            "Disconnected",
            gr.update(interactive=True),  # connect_btn
            gr.update(interactive=False),  # disconnect_btn
            gr.update(interactive=False),  # command_dropdown
            gr.update(interactive=False),  # data_input
            gr.update(interactive=False),  # send_btn
            [],  # איפוס היסטוריה
            gr.update(interactive=True),  # ip_input
            gr.update(interactive=True)  # port_input
        )


    def send_command(client, command, data, history):
        if not client or not client.connected:
            return (
                history,
                "Client is not connected.",
                client,
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update()
            )

        try:
            if data:
                message_data = data
            else:
                message_data = ""

            msg = ProtocolMessage(command, message_data)

            response = client.request(msg)

            if response.data:
                response_str = f"{response.command}: {response.data}"
            else:
                response_str = response.command

            if msg.data:
                request_str = f"{msg.command} {msg.data}"
            else:
                request_str = f"{msg.command}"

            history = history + [
                {"role": "user", "content": request_str},
                {"role": "assistant", "content": response_str}
            ]

            if command == "EXIT":
                client.close()

                return (
                    [],
                    "Disconnected (EXIT sent)",
                    None,  # מאפס את ה-client_state ל-None
                    gr.update(interactive=True),  # connect_btn חוזר להיות פעיל
                    gr.update(interactive=False),  # disconnect_btn מושבת
                    gr.update(interactive=False),  # command_dropdown מושבת
                    gr.update(interactive=False),  # send_btn מושבת
                    gr.update(interactive=True),  # ip_input
                    gr.update(interactive=True)  # port_input
                )

            return history, "", client, gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()

        except Exception as e:
            if data:
                error_data = data
            else:
                error_data = ""

            user_content = f"{command} {error_data}"

            history = history + [
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": f"Error: {e}"}
            ]
            return (
                history,
                f"Error occurred: {e}",
                client,
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update()
            )


    connect_btn.click(fn=connect_to_server, inputs=[ip_input, port_input, chatbot], outputs=[client_state, status_box, ip_input, port_input, connect_btn, disconnect_btn, command_dropdown, data_input, send_btn, chatbot])

    disconnect_btn.click(fn=disconnect_from_server, inputs=[client_state], outputs=[client_state, status_box, connect_btn, disconnect_btn, command_dropdown, data_input, send_btn, chatbot, ip_input, port_input])

    send_btn.click(fn=send_command, inputs=[client_state, command_dropdown, data_input, chatbot], outputs=[chatbot, status_box, client_state, connect_btn, disconnect_btn, command_dropdown, send_btn, ip_input, port_input])

    command_dropdown.change(fn=visible_data, inputs=command_dropdown, outputs=data_input)


    def clear_history():
        return []

    clear_btn.click(fn=clear_history, inputs=None, outputs=chatbot)

if __name__ == "__main__":
    demo.launch(share=True)