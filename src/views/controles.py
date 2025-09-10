import streamlit as st
import roslibpy
import streamlit.components.v1 as components

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

# --- LISTENER DE TECLADO NATIVO ---
def keyboard_listener(key_to_watch: list, key_name: str):
    """
    Cria um componente invisível que escuta eventos de teclado globais.
    """
    # O código JavaScript que será executado no navegador do usuário
    javascript_code = f"""
    <script>
    document.addEventListener('keydown', function(event) {{
        // Lista de teclas que nos interessam
        const watchKeys = {key_to_watch};
        
        // Verifica se a tecla pressionada está na nossa lista
        if (watchKeys.includes(event.key)) {{
            // Impede a ação padrão do navegador (ex: rolar a página com as setas)
            event.preventDefault();
            
            // Envia o nome da tecla de volta para o Python/Streamlit
            window.parent.postMessage({{
                isStreamlitMessage: true,
                type: "SET_COMPONENT_VALUE",
                key: "{key_name}",
                value: event.key
            }}, "*");
        }}
    }});
    </script>
    """
    # Renderiza o componente HTML/JS e retorna o valor enviado pelo JavaScript
    pressed_key = components.html(javascript_code, height=0, width=0)
    return pressed_key

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

    # --- CONTROLE VIA TECLADO GLOBAL ---
    st.info("Use as teclas W, A, S, D ou as Setas para controlar. Pressione Espaço para parar.")

    # Lista de teclas que o listener observa
    keys_to_watch = ['w', 's', 'a', 'd', 'up', 'down', 'left', 'right', 'space']
    pressed_key = keyboard_listener(key_to_watch=keys_to_watch, key_name="keyboard_listener_unique_key")    

    movimento_desejado = None

    # Input do Teclado
    if pressed_key:
        if pressed_key in ('w', 'ArrowUp'):
            movimento_desejado = "FRENTE"
        elif pressed_key in ('s', 'ArrowDown'):
            movimento_desejado = "RE"
        elif pressed_key in ('a', 'ArrowLeft'):
            movimento_desejado = "ESQUERDA"
        elif pressed_key in ('d', 'ArrowRight'):
            movimento_desejado = "DIREITA"
        elif pressed_key == ' ':
            movimento_desejado = "PARAR"
    
    last_command = st.session_state.get('last_command', 'PARAR')

    up_label = "🔼" if last_command == "FRENTE" else "↑"
    down_label = "🔽" if last_command == "RE" else "↓"
    left_label = "◀️" if last_command == "ESQUERDA" else "←"
    right_label = "▶️" if last_command == "DIREITA" else "→"
    stop_label = "⏹️" if last_command == "PARAR" else "🟥"

    # PASSO 3: Usamos os rótulos dinâmicos para criar os botões
    _, dpad_col, _ = st.columns([1, 1.2, 1])
    with dpad_col:
        r1c1, r1c2, r1c3 = st.columns(3)
        if r1c2.button(up_label, use_container_width=True, key="up_btn"):
            movimento_desejado = "FRENTE"

        r2c1, r2c2, r2c3 = st.columns(3)
        if r2c1.button(left_label, use_container_width=True, key="left_btn"):
            movimento_desejado = "ESQUERDA"
        if r2c2.button(stop_label, use_container_width=True, key="stop_btn"):
            movimento_desejado = "PARAR"
        if r2c3.button(right_label, use_container_width=True, key="right_btn"):
            movimento_desejado = "DIREITA"

        r3c1, r3c2, r3c3 = st.columns(3)
        if r3c2.button(down_label, use_container_width=True, key="down_btn"):
            movimento_desejado = "RE"

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
        st.rerun()

    # Exibe o último comando enviado
    st.metric("Último Comando Enviado", st.session_state.get('last_command', 'Nenhum'))