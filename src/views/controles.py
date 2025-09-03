import streamlit as st
import roslibpy
from st_keyup import st_keyup

# A função auxiliar publish_cmd_vel continua a mesma de antes.
def publish_cmd_vel(publisher, linear_x=0.0, angular_z=0.0):
    """Cria e publica uma mensagem Twist no tópico /cmd_vel."""
    if not publisher:
        st.warning("Publicador do ROS não está inicializado.")
        return
    
    twist = roslibpy.Message({
        'linear': {'x': linear_x, 'y': 0.0, 'z': 0.0},
        'angular': {'x': 0.0, 'y': 0.0, 'z': angular_z}
    })
    
    publisher.publish(twist)
    print(f"Comando enviado: Linear X={linear_x}, Angular Z={angular_z}")


def show_controles():
    st.header("Controles")

    # --- Acessa o publicador ROS da sessão ---
    ros_client = st.session_state.get('ros_client', None)
    if 'cmd_vel_publisher' not in st.session_state:
        if ros_client and ros_client.is_connected:
            st.session_state.cmd_vel_publisher = roslibpy.Topic(
                ros_client, '/cmd_vel', 'geometry_msgs/Twist'
            )
        else:
            st.session_state.cmd_vel_publisher = None
    publisher = st.session_state.get('cmd_vel_publisher', None)
    
    if not publisher:
        st.error("Não foi possível inicializar o publicador. Verifique a conexão com o ROS.")
        return

    # --- Definição das Velocidades ---
    VELOCIDADE_LINEAR = 0.5
    VELOCIDADE_ANGULAR = 1.0

    # --- PASSO 1: DEFINIR UMA VARIÁVEL PARA A AÇÃO ---
    movimento_desejado = None

    # --- PASSO 2: CAPTURAR INPUTS E DEFINIR A AÇÃO ---
    
    # Input do Teclado
    key_pressed = st_keyup("Clique aqui e use o teclado (WASD, Setas, Espaço)", key="keyboard_input")
    if key_pressed:
        if key_pressed.upper() in ('W', 'ARROWUP'):
            movimento_desejado = "FRENTE"
        elif key_pressed.upper() in ('S', 'ARROWDOWN'):
            movimento_desejado = "RE"
        elif key_pressed.upper() in ('A', 'ARROWLEFT'):
            movimento_desejado = "ESQUERDA"
        elif key_pressed.upper() in ('D', 'ARROWRIGHT'):
            movimento_desejado = "DIREITA"
        elif key_pressed == ' ':
            movimento_desejado = "PARAR"

    # Input dos Botões Visuais (Layout D-Pad)
    st.markdown("### Controle Direcional")
    _, dpad_col, _ = st.columns([1, 1, 1])
    with dpad_col:
        r1c1, r1c2, r1c3 = st.columns(3)
        if r1c2.button("↑", use_container_width=True, key="up_btn"):
            movimento_desejado = "FRENTE"

        r2c1, r2c2, r2c3 = st.columns(3)
        if r2c1.button("←", use_container_width=True, key="left_btn"):
            movimento_desejado = "ESQUERDA"
        if r2c2.button("⏹️", use_container_width=True, key="stop_btn"):
            movimento_desejado = "PARAR"
        if r2c3.button("→", use_container_width=True, key="right_btn"):
            movimento_desejado = "DIREITA"

        r3c1, r3c2, r3c3 = st.columns(3)
        if r3c2.button("↓", use_container_width=True, key="down_btn"):
            movimento_desejado = "RE"

    # --- PASSO 3: PROCESSAMENTO CENTRALIZADO DA AÇÃO ---
    # Este bloco só executa se uma ação foi definida (pelo teclado OU por um botão)
    if movimento_desejado:
        if movimento_desejado == "FRENTE":
            publish_cmd_vel(publisher, linear_x=VELOCIDADE_LINEAR)
        elif movimento_desejado == "RE":
            publish_cmd_vel(publisher, linear_x=-VELOCIDADE_LINEAR)
        elif movimento_desejado == "ESQUERDA":
            publish_cmd_vel(publisher, angular_z=VELOCIDADE_ANGULAR)
        elif movimento_desejado == "DIREITA":
            publish_cmd_vel(publisher, angular_z=-VELOCIDADE_ANGULAR)
        elif movimento_desejado == "PARAR":
            publish_cmd_vel(publisher, linear_x=0.0, angular_z=0.0)
        
        # Atualiza o feedback visual
        st.session_state.last_command = movimento_desejado
        st.toast(f"Comando: {movimento_desejado}")

    # Exibe o último comando enviado
    last_command = st.session_state.get('last_command', 'Nenhum')
    st.metric("Último Comando Enviado", last_command)