# Para rodar o app, use o comando: python -m streamlit run .\src\views\main.py
import streamlit as st
import sys
from pathlib import Path
import time
import os

# Adiciona o diretório raiz ao PYTHONPATH
root_dir = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, root_dir)

# Imports absolutos
# Import do ros_handler será feito dentro de main() para evitar import circular
from src.views.parametrizacao import show_parametrizacao
from src.views.controles import show_controles

# Configuração da página com sidebar inicial expandida
st.set_page_config(page_title="Interface de Controle", layout="wide")

def main():

    # Import dinâmico via importlib + getattr para evitar ImportError em import circular
    import importlib
    ros_handler = importlib.import_module('src.handlers.ros_handler')
    initialize_ros_connection = getattr(ros_handler, 'initialize_ros_connection')
    enable_post = getattr(ros_handler, 'enable_post', None)
    disable_post = getattr(ros_handler, 'disable_post', None)
    is_post_enabled = getattr(ros_handler, 'is_post_enabled', lambda: False)

    # permite definir host/port do rosbridge pela UI (igual ao teste)
    host = st.sidebar.text_input("ROSBridge host", value=os.getenv('ROSBRIDGE_HOST', '192.168.1.11'))
    port = int(st.sidebar.number_input("ROSBridge port", value=int(os.getenv('ROSBRIDGE_PORT', '9090')), min_value=1, max_value=65535))

    # tenta conectar apenas se não houver cliente ou ele não estiver conectado
    if 'ros_client' not in st.session_state or not getattr(st.session_state.get('ros_client'), 'is_connected', False):
        with st.spinner(f'Conectando ao rosbridge {host}:{port}...'):
            try:
                result = initialize_ros_connection(host=host, port=port)
                if isinstance(result, tuple):
                    robot_state, map_state, ros_client, cmd_vel_pub = (result + (None,)*4)[:4]
                else:
                    robot_state = map_state = ros_client = cmd_vel_pub = None
            except Exception as e:
                robot_state = map_state = ros_client = cmd_vel_pub = None
                st.sidebar.error(f"Erro ao conectar: {e}")

            st.session_state.robot_state = robot_state
            st.session_state.map_state = map_state
            st.session_state.ros_client = ros_client
            st.session_state.cmd_vel_publisher = cmd_vel_pub
    else:
        # usa os objetos já guardados na sessão
        robot_state = st.session_state.get('robot_state', None)
        ros_client = st.session_state.get('ros_client', None)
        map_state = st.session_state.get('map_state', None)

    st.sidebar.title("Configurações")
    
    # Inicializa o estado do interruptor como True
    if 'auto_update_enabled' not in st.session_state:
        st.session_state.auto_update_enabled = True

    # Inicializa o estado do POST toggle na sessão com o valor atual
    if 'post_enabled' not in st.session_state:
        st.session_state.post_enabled = is_post_enabled()

    # Cria o widget de toggle e o vincula à variável da sessão
    st.session_state.auto_update_enabled = st.sidebar.toggle(
        "Habilitar atualização em tempo real", 
        value=st.session_state.auto_update_enabled,
        help="Quando ativado, os dados da interface são atualizados automaticamente."
    )

    # Toggle para habilitar/desabilitar envios POST (comunicação ROS)
    new_post_enabled = st.sidebar.toggle(
        "Habilitar envios ROS (POST)",
        value=st.session_state.post_enabled,
        help="Quando desativado, comandos não serão publicados no ROS."
    )

    # Atualiza o estado apenas quando houver mudança
    if new_post_enabled != st.session_state.post_enabled:
        st.session_state.post_enabled = new_post_enabled
        if new_post_enabled:
            if enable_post:
                enable_post()
        else:
            if disable_post:
                disable_post()
    
    st.sidebar.title("Navegação")
    # Menu de navegação
    menu = st.sidebar.selectbox(
        "Telas",
        ["Visualização", "Parametrização", "Controles"]
    )

    if menu == "Visualização":
        st.header("Visualização")
        
        # dá mais espaço para o mapa (ajuste a proporção se quiser)
        col1, col2 = st.columns([4, 2], gap="large")
 
        with col1:
            # Mostrar mapa gerado a partir de /map (OccupancyGrid). Fallback para imagem de simulação.
            map_state = st.session_state.get('map_state', None)

            if map_state:
                last_map = None
                try:
                    last_map = map_state.get_map()
                except Exception:
                    last_map = None

                if last_map and isinstance(last_map, dict) and 'data' in last_map and 'info' in last_map:
                    try:
                        import numpy as np
                        from PIL import Image

                        info = last_map.get('info', {})
                        width = int(info.get('width', 0))
                        height = int(info.get('height', 0))

                        data = np.array(last_map['data'], dtype=np.int16)
                        if data.size != width * height:
                            st.write("Dados do mapa com tamanho inesperado")
                        else:
                            # Mapear valores de ocupação para tons de cinza:
                            # -1 (unknown) -> 127, 0 (free) -> 255 (branco), 100 (occupied) -> 0 (preto)
                            img_arr = np.where(data == -1, 127,
                                               np.where(data == 0, 255, 0)).astype(np.uint8)
                            img_arr = img_arr.reshape((height, width))

                            # Ajuste de orientação se necessário (flip/transpose)
                            img_arr = np.flipud(img_arr)

                            # Converte para imagem em escala de cinza e exibe (sem overlay)
                            pil_img = Image.fromarray(img_arr).convert('L')
                            st.image(pil_img, caption="Mapa (/map)", width='stretch')
                    except Exception as e:
                        st.write(f"Erro ao gerar imagem do mapa: {e}")
                else:
                    # fallback: exibe imagem de simulação se mapa ainda não chegou
                    try:
                        image_path = Path(__file__).parent.parent.parent / "assets" / "Simulacao.png"
                        st.image(str(image_path), width='stretch')
                    except Exception:
                        st.write("Mapa: nenhum dado recebido ainda")
            else:
                # se map_state não inicializado, mostra a imagem de simulação ou mensagem
                try:
                    image_path = Path(__file__).parent.parent.parent / "assets" / "Simulacao.png"
                    st.image(str(image_path), width='stretch')
                except Exception:
                    st.write("Mapa: não inicializado")

        with col2:

            robot_state = st.session_state.get('robot_state', None)
            ros_client = st.session_state.get('ros_client', None)

            # Verifica se a conexão está ativa para decidir o que mostrar
            if robot_state and ros_client and ros_client.is_connected:
                # Se ONLINE, busca os dados em tempo real do objeto de estado
                linear, angular = robot_state.get_velocity()

                st.success("Online")
                st.metric(label="Velocidade Linear (m/s)", value=f"{linear:.4f}")
                st.metric(label="Velocidade Angular (rad/s)", value=f"{angular:.4f}")

                # --- Exibe pose do robô (mesma coluna, sem interferir no mapa) ---
                try:
                    # obtém pose compatível com diferentes RobotState
                    if hasattr(robot_state, 'get_pose') and callable(getattr(robot_state, 'get_pose')):
                        pos, ori = robot_state.get_pose()
                    else:
                        pos = getattr(robot_state, 'position', {'x':0.0,'y':0.0,'z':0.0})
                        ori = getattr(robot_state, 'orientation', {'x':0.0,'y':0.0,'z':0.0,'w':1.0})

                    # garante dicionários com floats (mas preserva representação via repr ao exibir)
                    def _f(d, k, default=0.0):
                        try:
                            return float(d.get(k, default)) if isinstance(d, dict) else default
                        except Exception:
                            return default

                    px = _f(pos, 'x')
                    py = _f(pos, 'y')
                    pz = _f(pos, 'z')
                    ox = _f(ori, 'x')
                    oy = _f(ori, 'y')
                    oz = _f(ori, 'z')
                    ow = _f(ori, 'w', 1.0)

                    # Exibe apenas translation e rotation (mínimo e limpo)
                    st.markdown("**Pose (map frame)**")
                    st.text(f"translation:  x: {repr(px)},  y: {repr(py)},  z: {repr(pz)}")
                    st.text(f"rotation:     x: {repr(ox)},  y: {repr(oy)},  z: {repr(oz)},  w: {repr(ow)}")
                except Exception as e:
                    st.write("Erro ao obter pose:", e)
            else:
                # Se OFFLINE, mostra os valores padrão
                st.error("Offline")
                st.metric(label="Velocidade Linear (m/s)", value="0.0")
                st.metric(label="Velocidade Angular (rad/s)", value="0.0")

                # Debug: mostra status da conexão e idade do último update
                connected = bool(ros_client and getattr(ros_client, 'is_connected', False))
                st.write(f"ROSBridge {host}:{port} — connected: {connected}")
                last_update = getattr(st.session_state.get('robot_state', None), 'last_update', None)
                if last_update:
                    st.write(f"Último update: {time.time() - last_update:.2f}s atrás")

# ----------------------------------------- Parametrização ------------------------------------------------        
    elif menu == "Parametrização":
        show_parametrizacao()

# ----------------------------------------- Controles ------------------------------------------------        
    elif menu == "Controles":
        show_controles()

if __name__ == "__main__":
    main()

    if st.session_state.get('auto_update_enabled', False):
        # Força a página a recarregar e atualizar os dados a cada meio segundo.
        try:
            time.sleep(0.5)
            st.rerun()
        except Exception as e:
            # Evita erros se a conexão for fechada abruptamente
            st.stop()