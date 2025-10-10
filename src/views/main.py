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
    # substitua o bloco de inicialização/armazenamento na sessão pela versão abaixo
    import os
    host = st.sidebar.text_input("ROSBridge host", value=os.getenv('ROSBRIDGE_HOST', '192.168.1.11'))
    port = int(st.sidebar.number_input("ROSBridge port", value=int(os.getenv('ROSBRIDGE_PORT', '9090')), min_value=1, max_value=65535))

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
        robot_state = st.session_state.get('robot_state', None)
        ros_client = st.session_state.get('ros_client', None)
        map_state = st.session_state.get('map_state', None)
        # garantir que o publisher também esteja disponível na sessão
        if 'cmd_vel_publisher' not in st.session_state:
            st.session_state.cmd_vel_publisher = None

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
            # Obtém estado do mapa da sessão
            map_state = st.session_state.get('map_state')
            
            if map_state:
                try:
                    last_map = map_state.get_map()
                    last_update = getattr(map_state, 'last_update', None)
                    
                    if last_map and isinstance(last_map, dict) and 'data' in last_map and 'info' in last_map:
                        try:
                            import numpy as np
                            from PIL import Image

                            info = last_map.get('info', {})
                            width = int(info.get('width', 0))
                            height = int(info.get('height', 0))

                            data = np.array(last_map['data'], dtype=np.int16)
                            if data.size == width * height:
                                # Converte dados de ocupação para imagem em escala de cinza
                                img_arr = np.where(data == -1, 127,
                                               np.where(data == 0, 255, 0)).astype(np.uint8)
                                img_arr = img_arr.reshape((height, width))
                                img_arr = np.flipud(img_arr)
                                
                                # Converte para PIL e exibe
                                pil_img = Image.fromarray(img_arr).convert('L')

                                # --- Overlay: marcador da posição do robô ---
                                try:
                                    robot_state = st.session_state.get('robot_state', None)
                                    if robot_state and hasattr(robot_state, 'get_pose'):
                                        pos, ori = robot_state.get_pose()
                                    else:
                                        pos = getattr(robot_state, 'position', {'x': 0.0, 'y': 0.0, 'z': 0.0}) if robot_state else {'x':0.0,'y':0.0,'z':0.0}

                                    # Parâmetros do mapa
                                    resolution = float(info.get('resolution', 0.05))
                                    origin = info.get('origin', {}) or {}
                                    origin_pos = origin.get('position', origin) if isinstance(origin, dict) else {}
                                    origin_ori = origin.get('orientation', {}) if isinstance(origin, dict) else {}
                                    ox = float(origin_pos.get('x', 0.0))
                                    oy = float(origin_pos.get('y', 0.0))
                                    # Yaw do origin (se o mapa estiver rotacionado)
                                    try:
                                        ox_q = float(origin_ori.get('x', 0.0))
                                        oy_q = float(origin_ori.get('y', 0.0))
                                        oz_q = float(origin_ori.get('z', 0.0))
                                        ow_q = float(origin_ori.get('w', 1.0))
                                        import math
                                        yaw0 = math.atan2(2.0*(ow_q*oz_q + ox_q*oy_q), 1.0 - 2.0*(oy_q*oy_q + oz_q*oz_q))
                                    except Exception:
                                        yaw0 = 0.0

                                    # Posição do robô em metros (frame map, após composição no handler)
                                    rx = float(pos.get('x', 0.0))
                                    ry = float(pos.get('y', 0.0))

                                    # Converte para sistema do mapa: traduz para a origem e remove rotação do origin
                                    dx = rx - ox
                                    dy = ry - oy
                                    if abs(yaw0) > 1e-6:
                                        cy, sy = math.cos(-yaw0), math.sin(-yaw0)
                                        mx = cy*dx - sy*dy
                                        my = sy*dx + cy*dy
                                    else:
                                        mx, my = dx, dy

                                    # Metros -> pixels
                                    px = int(mx / resolution)
                                    py = int(my / resolution)

                                    # Ajuste por flip vertical feito em img_arr (flipud)
                                    py_disp = (height - 1) - py

                                    if 0 <= px < width and 0 <= py_disp < height:
                                        from PIL import ImageDraw
                                        pil_rgb = pil_img.convert('RGB')
                                        draw = ImageDraw.Draw(pil_rgb)
                                        r = 5
                                        draw.ellipse([(px - r, py_disp - r), (px + r, py_disp + r)], fill=(255, 0, 0))
                                        pil_to_show = pil_rgb
                                    else:
                                        pil_to_show = pil_img
                                except Exception:
                                    pil_to_show = pil_img

                                st.image(pil_to_show, caption="Mapa (/map)", width='stretch')
                                

                                # Mostra idade da última atualização
                                if last_update:
                                    age = time.time() - last_update
                                    st.caption(f"Última atualização: {age:.1f}s atrás")
                            else:
                                st.warning("Tamanho dos dados do mapa inconsistente")
                        except Exception as e:
                            st.error(f"Erro ao processar mapa: {e}")
                    else:
                        # Mostra imagem de fallback
                        image_path = Path(__file__).parent.parent.parent / "assets" / "Simulacao.png"
                        if image_path.exists():
                            st.image(str(image_path), width='stretch')
                        else:
                            st.warning("Nenhum dado do mapa recebido ainda")
                except Exception as e:
                    st.error(f"Erro ao acessar mapa: {e}")
            else:
                st.warning("Estado do mapa não inicializado")

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
                    # obtém pose do estado
                    if hasattr(robot_state, 'get_pose') and callable(getattr(robot_state, 'get_pose')):
                        pos, ori = robot_state.get_pose()
                    else:
                        pos = getattr(robot_state, 'position', {'x': 0.0, 'y': 0.0, 'z': 0.0})
                        ori = getattr(robot_state, 'orientation', {'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 1.0})

                    def _fv(d, k, default=0.0):
                        try:
                            return float(d.get(k, default)) if isinstance(d, dict) else default
                        except Exception:
                            return default

                    # valores numéricos (como float) e exibição com repr para preservar notação
                    px = _fv(pos, 'x'); py = _fv(pos, 'y'); pz = _fv(pos, 'z')
                    ox = _fv(ori, 'x'); oy = _fv(ori, 'y'); oz = _fv(ori, 'z'); ow = _fv(ori, 'w', 1.0)

                    # Exibição em seções para caber o valor inteiro na tela
                    st.markdown("**Translation**")
                    st.text(f"X: {repr(px)}")
                    st.text(f"Y: {repr(py)}")
                    st.text(f"Z: {repr(pz)}")

                    st.markdown("**Rotation**")
                    st.text(f"x: {repr(ox)}")
                    st.text(f"y: {repr(oy)}")
                    st.text(f"z: {repr(oz)}")
                    st.text(f"w: {repr(ow)}")
                except Exception as e:
                    st.write("Erro ao exibir pose:", e)
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