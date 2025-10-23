import streamlit as st
import roslibpy
import streamlit.components.v1 as components
import json
import threading
import time

# from src.handlers.ros_handler import send_velocity_command 

def _ensure_advertised(topic: roslibpy.Topic):
    try:
        if not getattr(topic, 'is_advertised', False):
            topic.advertise()
    except Exception:
        # versões antigas não possuem is_advertised
        try:
            topic.advertise()
        except Exception:
            pass

# A função auxiliar publish_cmd_vel continua a mesma de antes.
def publish_cmd_vel(publisher, linear_x=0.0, angular_z=0.0):
    """Cria e publica uma mensagem Twist no tópico /cmd_vel."""
    if not publisher:
        st.warning("Publicador do ROS não está inicializado.")
        return
    _ensure_advertised(publisher)
    twist = roslibpy.Message({
        'linear': {'x': float(linear_x), 'y': 0.0, 'z': 0.0},
        'angular': {'x': 0.0, 'y': 0.0, 'z': float(angular_z)}
    })
    try:
        publisher.publish(twist)
    except Exception as e:
        st.warning(f"Falha ao publicar /cmd_vel: {e}")

# --- Worker de teleop: publica continuamente até mudar o comando ---
def _teleop_worker(stop_event: threading.Event):
    rate_hz = 10.0
    dt = 1.0 / rate_hz
    while not stop_event.is_set():
        publisher = st.session_state.get('cmd_vel_publisher', None)
        cmd = st.session_state.get('teleop_command', 'PARAR')
        lin, ang = 0.0, 0.0
        if cmd == "FRENTE":
            lin = st.session_state.get('TELEOP_VEL_LINEAR', 0.5)
        elif cmd == "RE":
            lin = -st.session_state.get('TELEOP_VEL_LINEAR', 0.5)
        elif cmd == "ESQUERDA":
            ang = st.session_state.get('TELEOP_VEL_ANGULAR', 1.0)
        elif cmd == "DIREITA":
            ang = -st.session_state.get('TELEOP_VEL_ANGULAR', 1.0)
        if publisher:
            publish_cmd_vel(publisher, lin, ang)
        time.sleep(dt)

# --- LISTENER DE TECLADO NATIVO ---
def keyboard_listener(key_to_watch: list, key_name: str):
    """
    Cria um componente invisível que escuta eventos de teclado globais.
    Retorna o último evento registrado no st.session_state[key_name], se houver.
    """
    javascript_code = f"""
    <script>
    const pressedKeys = new Set();
    const sendDataToStreamlit = (data) => {{
        window.parent.postMessage({{
            isStreamlitMessage: true,
            type: "SET_COMPONENT_VALUE",
            key: "{key_name}",
            value: data
        }}, "*");
    }};
    document.addEventListener('keydown', function(event) {{
        const watchKeys = {json.dumps(key_to_watch)};
        if (watchKeys.includes(event.key) && !pressedKeys.has(event.key)) {{
            event.preventDefault();
            pressedKeys.add(event.key);
            sendDataToStreamlit({{type: 'keydown', key: event.key}});
        }}
    }});
    document.addEventListener('keyup', function(event) {{
        const watchKeys = {json.dumps(key_to_watch)};
        if (watchKeys.includes(event.key)) {{
            event.preventDefault();
            pressedKeys.delete(event.key);
            sendDataToStreamlit({{type: 'keyup', key: event.key}});
        }}
    }});
    </script>
    """
    components.html(javascript_code, height=0, width=0)
    return st.session_state.get(key_name)

def _set_teleop_command(cmd: str):
    st.session_state.teleop_command = cmd
    st.session_state.last_command = cmd

def show_controles():
    st.header("Controles")

    # --- Acessa o publicador ROS da sessão ---
    ros_client = st.session_state.get('ros_client', None)
    if 'cmd_vel_publisher' not in st.session_state:
        if ros_client and ros_client.is_connected:
            # ROS 2 via rosbridge usa 'geometry_msgs/msg/Twist'
            topic = roslibpy.Topic(ros_client, '/cmd_vel', 'geometry_msgs/msg/Twist')
            _ensure_advertised(topic)
            st.session_state.cmd_vel_publisher = topic
        else:
            st.session_state.cmd_vel_publisher = None

    publisher = st.session_state.get('cmd_vel_publisher', None)
    if not publisher:
        st.error("Não foi possível inicializar o publicador. Verifique a conexão com o ROS.")
        return

    # Velocidades padrão
    st.session_state.setdefault('TELEOP_VEL_LINEAR', 0.5)
    st.session_state.setdefault('TELEOP_VEL_ANGULAR', 1.0)

    # Estado do teleop
    st.session_state.setdefault('teleop_command', 'PARAR')
    st.session_state.setdefault('last_command', 'PARAR')

    # Inicia o worker de teleop (uma vez)
    if 'teleop_stop_event' not in st.session_state:
        st.session_state.teleop_stop_event = threading.Event()
    if 'teleop_thread' not in st.session_state or not st.session_state.teleop_thread.is_alive():
        st.session_state.teleop_thread = threading.Thread(
            target=_teleop_worker, args=(st.session_state.teleop_stop_event,),
            daemon=True
        )
        st.session_state.teleop_thread.start()

    st.info("Use as teclas W, A, S, D ou as Setas para controlar. Pressione Espaço para parar.")

    # Teclas observadas
    keys_to_watch = ['w', 's', 'a', 'd', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' ']
    key_event = keyboard_listener(key_to_watch=keys_to_watch, key_name="keyboard_listener_unique_key")

    # Processa eventos de teclado (altera comando; publicação é contínua no worker)
    if key_event and isinstance(key_event, dict) and key_event.get('type') == 'keydown':
        k = key_event.get('key')
        if k in ('w', 'ArrowUp'):
            _set_teleop_command("FRENTE")
        elif k in ('s', 'ArrowDown'):
            _set_teleop_command("RE")
        elif k in ('a', 'ArrowLeft'):
            _set_teleop_command("ESQUERDA")
        elif k in ('d', 'ArrowRight'):
            _set_teleop_command("DIREITA")
        elif k == ' ':
            _set_teleop_command("PARAR")

    # Botões (também alteram o comando; o worker mantém o envio)
    last_command = st.session_state.get('last_command', 'PARAR')
    up_label = "🔼" if last_command == "FRENTE" else "↑"
    down_label = "🔽" if last_command == "RE" else "↓"
    left_label = "◀️" if last_command == "ESQUERDA" else "←"
    right_label = "▶️" if last_command == "DIREITA" else "→"
    stop_label = "⏹️" if last_command == "PARAR" else "🟥"

    _, dpad_col, _ = st.columns([1, 1.2, 1])
    with dpad_col:
        r1c1, r1c2, r1c3 = st.columns(3)
        if r1c2.button(up_label, width='stretch', key="up_btn"):
            _set_teleop_command("FRENTE")

        r2c1, r2c2, r2c3 = st.columns(3)
        if r2c1.button(left_label, width='stretch', key="left_btn"):
            _set_teleop_command("ESQUERDA")
        if r2c2.button(stop_label, width='stretch', key="stop_btn"):
            _set_teleop_command("PARAR")
        if r2c3.button(right_label, width='stretch', key="right_btn"):
            _set_teleop_command("DIREITA")

        r3c1, r3c2, r3c3 = st.columns(3)
        if r3c2.button(down_label, width='stretch', key="down_btn"):
            _set_teleop_command("RE")

    # Feedback
    st.metric("Último Comando Enviado", st.session_state.get('last_command', 'Nenhum'))