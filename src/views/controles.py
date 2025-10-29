import streamlit as st
import roslibpy
import streamlit.components.v1 as components
import json
import threading
import time

# ---------------------- Estado compartilhado (thread-safe) ----------------------
teleop_state = {
    'enabled': False,   # controle manual ligado?
    'cmd': 'PARAR',     # FRENTE | RE | ESQUERDA | DIREITA | PARAR
    'v_lin': 0.5,       # m/s (limite)
    'v_ang': 1.0        # rad/s (limite)
}
_state_lock = threading.Lock()


class PublisherBox:
    """Container mutável para o publisher (sem acessar st.*)"""
    def __init__(self, obj=None):
        self.obj = obj


# ----------------------------- Utilidades ROS -----------------------------
def _ensure_advertised(topic: roslibpy.Topic):
    try:
        if not getattr(topic, 'is_advertised', False):
            topic.advertise()
    except Exception:
        try:
            topic.advertise()
        except Exception:
            pass


def _publish_cmd_vel_silent(publisher, linear_x=0.0, angular_z=0.0):
    """Publica Twist sem usar Streamlit (para thread)"""
    if not publisher:
        return
    try:
        _ensure_advertised(publisher)
        msg = roslibpy.Message({
            'linear': {'x': float(linear_x), 'y': 0.0, 'z': 0.0},
            'angular': {'x': 0.0, 'y': 0.0, 'z': float(angular_z)}
        })
        publisher.publish(msg)
    except Exception:
        pass


def _compute_cmd_vel(cmd: str, v_lin_max: float, v_ang_max: float):
    """
    Regras:
    - Frente:   linear = v_lin_max, angular = 0
    - Ré:       linear = -v_lin_max, angular = 0
    - Esquerda: linear = v_ang_max, angular = v_ang_max
    - Direita:  linear = v_ang_max, angular = -v_ang_max
    - Parar:    linear = 0, angular = 0
    """
    v_lin_max = float(v_lin_max)
    v_ang_max = float(v_ang_max)
    if cmd == "FRENTE":
        return v_lin_max, 0.0
    if cmd == "RE":
        return -v_lin_max, 0.0
    if cmd == "ESQUERDA":
        return v_ang_max, v_ang_max
    if cmd == "DIREITA":
        return v_ang_max, -v_ang_max
    return 0.0, 0.0


# -------------------------------- Worker thread --------------------------------
def _teleop_worker(pub_box: PublisherBox, stop_event: threading.Event):
    """Publica a cada 0.1s (10 Hz) sem usar st.*"""
    rate_hz = 50.0
    dt = 1.0 / rate_hz
    last_enabled = False

    while not stop_event.is_set():
        with _state_lock:
            enabled = bool(teleop_state['enabled'])
            cmd = teleop_state['cmd']
            v_lin = float(teleop_state['v_lin'])
            v_ang = float(teleop_state['v_ang'])

        pub = pub_box.obj

        # Se desabilitou agora, envia parada uma vez
        if not enabled:
            if last_enabled and pub:
                _publish_cmd_vel_silent(pub, 0.0, 0.0)
            last_enabled = False
            time.sleep(dt)
            continue

        last_enabled = True

        lin, ang = _compute_cmd_vel(cmd, v_lin, v_ang)
        if pub:
            _publish_cmd_vel_silent(pub, lin, ang)

        time.sleep(dt)


# --------------------------- Listener de teclado ---------------------------
def keyboard_listener(key_to_watch: list, key_name: str):
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
    # Atualiza UI
    st.session_state.teleop_command = cmd
    st.session_state.last_command = cmd
    # Atualiza thread
    with _state_lock:
        teleop_state['cmd'] = cmd


# ------------------------------------- UI -------------------------------------
def show_controles():
    st.header("Controles")

    # Toggle controle manual
    if 'teleop_enabled' not in st.session_state:
        st.session_state['teleop_enabled'] = False
    prev_enabled = st.session_state.get('_teleop_enabled_prev', st.session_state['teleop_enabled'])

    # Publisher ROS
    ros_client = st.session_state.get('ros_client', None)
    if 'cmd_vel_publisher' not in st.session_state:
        if ros_client and getattr(ros_client, 'is_connected', False):
            topic = roslibpy.Topic(ros_client, '/cmd_vel', 'geometry_msgs/msg/Twist')
            _ensure_advertised(topic)
            st.session_state.cmd_vel_publisher = topic
        else:
            st.session_state.cmd_vel_publisher = None
    publisher = st.session_state.get('cmd_vel_publisher', None)

    # Holder para a thread
    if 'teleop_pub_box' not in st.session_state:
        st.session_state['teleop_pub_box'] = PublisherBox(None)
    pub_box = st.session_state['teleop_pub_box']
    pub_box.obj = publisher

    if not publisher:
        st.error("Não foi possível inicializar o publicador. Verifique a conexão com o ROS.")
        return

    st.subheader("Controle manual")
    st.toggle("Ativar controle manual", key="teleop_enabled")
    cur_enabled = st.session_state.get('teleop_enabled', False)
    st.session_state['_teleop_enabled_prev'] = cur_enabled

    # Reflete na thread
    with _state_lock:
        teleop_state['enabled'] = bool(cur_enabled)

    if prev_enabled and not cur_enabled:
        _set_teleop_command("PARAR")

    # Velocidades
    st.session_state.setdefault('TELEOP_VEL_LINEAR', 1.0)
    st.session_state.setdefault('TELEOP_VEL_ANGULAR', 0.5)
    with _state_lock:
        teleop_state['v_lin'] = float(st.session_state['TELEOP_VEL_LINEAR'])
        teleop_state['v_ang'] = float(st.session_state['TELEOP_VEL_ANGULAR'])

    # Comando
    st.session_state.setdefault('teleop_command', 'PARAR')
    st.session_state.setdefault('last_command', 'PARAR')
    with _state_lock:
        teleop_state['cmd'] = st.session_state['teleop_command']

    # Thread (uma vez)
    if 'teleop_stop_event' not in st.session_state:
        st.session_state['teleop_stop_event'] = threading.Event()
    if 'teleop_thread' not in st.session_state or not st.session_state.teleop_thread.is_alive():
        st.session_state.teleop_thread = threading.Thread(
            target=_teleop_worker, args=(pub_box, st.session_state.teleop_stop_event), daemon=True
        )
        st.session_state.teleop_thread.start()

    if cur_enabled:
        st.info("Clique nos botões para controlar o robô (publica a cada 0.1s)")
    else:
        st.warning("Controle manual desativado.")

    # Teclado
    keys_to_watch = ['w', 's', 'a', 'd', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' ']
    key_event = None if not cur_enabled else keyboard_listener(
        key_to_watch=keys_to_watch, key_name="keyboard_listener_unique_key"
    )

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
        st.rerun()

    # Ícones
    last_cmd = st.session_state.get('last_command', 'PARAR')
    up_label = "🔼" if last_cmd == "FRENTE" else "↑"
    down_label = "🔽" if last_cmd == "RE" else "↓"
    left_label = "◀️" if last_cmd == "ESQUERDA" else "←"
    right_label = "▶️" if last_cmd == "DIREITA" else "→"
    stop_label = "⏹️" if last_cmd == "PARAR" else "🟥"

    # CSS para botões maiores
    st.markdown("""
        <style>
        div[data-testid="column"] button {
            height: 100px !important;
            font-size: 48px !important;
            padding: 20px !important;
        }
        div[data-testid="column"] button p {
            font-size: 48px !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Botões
    _, dpad_col, _ = st.columns([1, 1.2, 1])
    with dpad_col:
        r1c1, r1c2, r1c3 = st.columns(3)
        with r1c2:
            if st.button(up_label, key="up_btn", disabled=not cur_enabled, use_container_width=True):
                _set_teleop_command("FRENTE")
                st.rerun()

        r2c1, r2c2, r2c3 = st.columns(3)
        with r2c1:
            if st.button(left_label, key="left_btn", disabled=not cur_enabled, use_container_width=True):
                _set_teleop_command("ESQUERDA")
                st.rerun()
        with r2c2:
            if st.button(stop_label, key="stop_btn", disabled=not cur_enabled, use_container_width=True):
                _set_teleop_command("PARAR")
                st.rerun()
        with r2c3:
            if st.button(right_label, key="right_btn", disabled=not cur_enabled, use_container_width=True):
                _set_teleop_command("DIREITA")
                st.rerun()

        r3c1, r3c2, r3c3 = st.columns(3)
        with r3c2:
            if st.button(down_label, key="down_btn", disabled=not cur_enabled, use_container_width=True):
                _set_teleop_command("RE")
                st.rerun()

    # Feedback
    st.metric("Último Comando Enviado", st.session_state.get('last_command', 'Nenhum'))

    # Ajustes de velocidade
    st.markdown("**Ajustes de velocidade**")
    col_v1, col_v2 = st.columns(2)
    with col_v1:
        v_lin = st.slider(
            "Velocidade Linear Máxima (m/s)", min_value=0.0, max_value=2.0,
            value=float(st.session_state.get('TELEOP_VEL_LINEAR', 0.5)), step=0.05
        )
    with col_v2:
        v_ang = st.slider(
            "Velocidade Angular Máxima (rad/s)", min_value=0.0, max_value=1.0,
            value=float(st.session_state.get('TELEOP_VEL_ANGULAR', 1.0)), step=0.05
        )
    st.session_state['TELEOP_VEL_LINEAR'] = float(v_lin)
    st.session_state['TELEOP_VEL_ANGULAR'] = float(v_ang)
    with _state_lock:
        teleop_state['v_lin'] = float(v_lin)
        teleop_state['v_ang'] = float(v_ang)