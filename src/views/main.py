# Para rodar o app, use o comando: python -m streamlit run .\src\views\main.py
import streamlit as st
import sys
from pathlib import Path
import time
import os
import math

# Adiciona o diretório raiz ao PYTHONPATH
root_dir = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, root_dir)

# Imports absolutos
# Import do ros_handler será feito dentro de main() para evitar import circular
from src.views.parametrizacao import show_parametrizacao
from src.views.controles import show_controles

# Configuração da página com sidebar inicial expandida
st.set_page_config(page_title="Interface de Controle", layout="wide")

# +++ NOVO: clique na imagem + desenho do ponto clicado
try:
    from streamlit_image_coordinates import streamlit_image_coordinates as get_img_click
except Exception:
    get_img_click = None

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
    host = st.sidebar.text_input("ROSBridge host", value=os.getenv('ROSBRIDGE_HOST', '192.168.1.8'))
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
        col1, col2 = st.columns([4, 2], gap="large")

        with col1:
            map_state = st.session_state.get('map_state')

            # estado p/ waypoint temporário e modo seleção
            if 'pending_goal' not in st.session_state:
                st.session_state['pending_goal'] = None
            if 'wp_select_mode' not in st.session_state:
                st.session_state['wp_select_mode'] = True  # ativo por padrão

            # Linha com switch + botão Enviar waypoint
            s_col, b_col = st.columns([3, 1])
            with s_col:
                st.session_state['wp_select_mode'] = st.toggle(
                    "Modo seleção de waypoint (clicar no mapa)",
                    value=st.session_state['wp_select_mode']
                )
            with b_col:
                if st.button("Enviar waypoint", type="primary", width='stretch', key="btn_send_wp_top"):
                    # Publica o último waypoint temporário, se existir
                    pg = st.session_state.get('pending_goal')
                    if not pg:
                        st.warning("Nenhum waypoint temporário selecionado.")
                    else:
                        # Usa yaw escolhido anteriormente (se existir) ou o último yaw do robô como padrão
                        yaw_deg = st.session_state.get('wp_yaw_deg', 0.0)
                        yaw_rad = math.radians(float(yaw_deg))
                        # Publica via ros_handler.publish_goal_pose (com fallback)
                        import importlib
                        ros_handler = importlib.import_module('src.handlers.ros_handler')
                        publish_goal_pose = getattr(ros_handler, 'publish_goal_pose', None)

                        def _publish_goal_pose_fallback(x, y, yaw_r):
                            try:
                                import roslibpy, time as _t
                                client = st.session_state.get('ros_client')
                                if not client or not getattr(client, 'is_connected', False):
                                    return False
                                topic = roslibpy.Topic(client, '/goal_pose', 'geometry_msgs/PoseStamped')
                                now = _t.time(); sec = int(now); nsec = int((now - sec) * 1e9)
                                qz = math.sin(yaw_r/2.0); qw = math.cos(yaw_r/2.0)
                                msg = roslibpy.Message({
                                    'header': {'frame_id': 'map', 'stamp': {'sec': sec, 'nanosec': nsec}},
                                    'pose': {
                                        'position': {'x': float(x), 'y': float(y), 'z': 0.0},
                                        'orientation': {'x': 0.0, 'y': 0.0, 'z': qz, 'w': qw}
                                    }
                                })
                                topic.publish(msg)
                                return True
                            except Exception:
                                return False

                        ok = False
                        try:
                            if callable(publish_goal_pose):
                                ok = publish_goal_pose(pg['x'], pg['y'], yaw_rad,
                                                       frame_id='map', topic_name='/goal_pose',
                                                       goal_pub=getattr(st.session_state.get('robot_state', None), 'goal_pose_pub', None),
                                                       client=st.session_state.get('ros_client'))
                        except Exception:
                            ok = False
                        if not ok:
                            ok = _publish_goal_pose_fallback(pg['x'], pg['y'], yaw_rad)

                        if ok:
                            st.success("Waypoint publicado em /goal_pose.")
                        else:
                            st.error("Falha ao publicar em /goal_pose.")

            if get_img_click is None and st.session_state['wp_select_mode']:
                st.warning("Pacote 'streamlit-image-coordinates' não encontrado. Instale com: pip install streamlit-image-coordinates")

            if map_state:
                try:
                    last_map = map_state.get_map()
                    last_update = getattr(map_state, 'last_update', None)

                    if last_map and isinstance(last_map, dict) and 'data' in last_map and 'info' in last_map:
                        try:
                            import numpy as np
                            from PIL import Image, ImageDraw

                            info = last_map.get('info', {})
                            width = int(info.get('width', 0))
                            height = int(info.get('height', 0))
                            resolution = float(info.get('resolution', 0.05))

                            data = np.array(last_map['data'], dtype=np.int16)
                            if data.size == width * height:
                                img_arr = np.where(data == -1, 127, np.where(data == 0, 255, 0)).astype(np.uint8)
                                img_arr = img_arr.reshape((height, width))
                                img_arr = np.flipud(img_arr)
                                pil_img = Image.fromarray(img_arr).convert('L')

                                # pose do robô e parâmetros do origin
                                robot_state = st.session_state.get('robot_state', None)
                                if robot_state and hasattr(robot_state, 'get_pose'):
                                    pos, ori = robot_state.get_pose()
                                else:
                                    pos = {'x': 0.0, 'y': 0.0, 'z': 0.0}
                                    ori = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 1.0}

                                origin = info.get('origin', {}) or {}
                                origin_pos = origin.get('position', origin) if isinstance(origin, dict) else {}
                                origin_ori = origin.get('orientation', {}) if isinstance(origin, dict) else {}
                                ox = float(origin_pos.get('x', 0.0))
                                oy = float(origin_pos.get('y', 0.0))

                                try:
                                    ox_q = float(origin_ori.get('x', 0.0))
                                    oy_q = float(origin_ori.get('y', 0.0))
                                    oz_q = float(origin_ori.get('z', 0.0))
                                    ow_q = float(origin_ori.get('w', 1.0))
                                    yaw0 = math.atan2(2.0*(ow_q*oz_q + ox_q*oy_q), 1.0 - 2.0*(oy_q*oy_q + oz_q*oz_q))
                                except Exception:
                                    yaw0 = 0.0

                                rx = float(pos.get('x', 0.0)); ry = float(pos.get('y', 0.0))
                                qx = float(ori.get('x', 0.0)); qy = float(ori.get('y', 0.0))
                                qz = float(ori.get('z', 0.0)); qw = float(ori.get('w', 1.0))

                                # map->pixels (compensando rotação do origin)
                                dx = rx - ox; dy = ry - oy
                                if abs(yaw0) > 1e-6:
                                    cy, sy = math.cos(-yaw0), math.sin(-yaw0)
                                    mx = cy*dx - sy*dy
                                    my = sy*dx + cy*dy
                                else:
                                    mx, my = dx, dy
                                px = int(round(mx / resolution))
                                py = int(round(my / resolution))

                                # yaw do robô para desenhar seta
                                try:
                                    yaw_robot = math.atan2(2.0*(qw*qz + qx*qy), 1.0 - 2.0*(qy*qy + qz*qz))
                                except Exception:
                                    yaw_robot = 0.0
                                yaw_disp = yaw_robot - yaw0
                                if yaw_disp > math.pi: yaw_disp -= 2.0*math.pi
                                if yaw_disp < -math.pi: yaw_disp += 2.0*math.pi

                                # desenha seta
                                def disp_y(y_pix): return (height - 1) - y_pix
                                L_pix = max(16, int(round(0.5 / max(resolution, 1e-6))))
                                base_w = max(12, int(round(L_pix * 0.65)))
                                back_off = int(round(L_pix * 0.35))
                                c = math.cos(yaw_disp); s = math.sin(yaw_disp)
                                ax = px + int(round(L_pix * c)); ay = py + int(round(L_pix * s))
                                bx = px - int(round(back_off * c)); by = py - int(round(back_off * s))
                                half_w = base_w // 2
                                lx = bx + int(round(half_w * (-s))); ly = by + int(round(half_w * ( c)))
                                rx_ = bx - int(round(half_w * (-s))); ry_ = by - int(round(half_w * ( c)))
                                p_apex  = (ax,  disp_y(ay))
                                p_left  = (lx,  disp_y(ly))
                                p_right = (rx_, disp_y(ry_))
                                pil_rgb = pil_img.convert('RGB')
                                draw = ImageDraw.Draw(pil_rgb)
                                tri = [p_apex, p_right, p_left]
                                draw.polygon(tri, fill=(245,179,66))
                                draw.line(tri + [tri[0]], fill=(0,0,0), width=2)
                                pil_to_show = pil_rgb

                                # Imagem clicável para waypoint temporário
                                if st.session_state['wp_select_mode'] and get_img_click is not None:
                                    st.caption("Clique no mapa para escolher o waypoint temporário")
                                    click = get_img_click(pil_to_show, key="map_click_wp", width='stretch')

                                    if click:
                                        # Reescala para coordenadas originais
                                        disp_w = click.get("width") or width
                                        disp_h = click.get("height") or height
                                        cx_disp = float(click["x"])
                                        cy_disp = float(click["y"])
                                        scale_x = width / float(disp_w)
                                        scale_y = height / float(disp_h)
                                        px_pix = int(round(cx_disp * scale_x))
                                        py_pix_img = int(round(cy_disp * scale_y))

                                        # Marca o ponto
                                        marked = pil_to_show.copy()
                                        dm = ImageDraw.Draw(marked)
                                        r = max(4, 6)
                                        dm.ellipse([(px_pix - r, py_pix_img - r), (px_pix + r, py_pix_img + r)],
                                                   outline=(0,255,0), width=3)
                                        st.image(marked, caption="Mapa (/map)", width='stretch')

                                        # Converte para coordenadas do mapa (desfaz flip)
                                        py_pix = int(round((height - 1) - py_pix_img))
                                        mx_goal = px_pix * resolution
                                        my_goal = py_pix * resolution
                                        if abs(yaw0) > 1e-6:
                                            c0, s0 = math.cos(yaw0), math.sin(yaw0)
                                            dx_g = c0*mx_goal - s0*my_goal
                                            dy_g = s0*mx_goal + c0*my_goal
                                        else:
                                            dx_g, dy_g = mx_goal, my_goal
                                        gx = ox + dx_g
                                        gy = oy + dy_g

                                        st.session_state['pending_goal'] = {'x': gx, 'y': gy}
                                        # Atualiza yaw sugerido (para o input abaixo e para o botão superior)
                                        st.session_state['wp_yaw_deg'] = float(math.degrees(yaw_robot))
                                    else:
                                        # mostra o mapa normalmente quando ainda não clicou
                                        st.image(pil_to_show, caption="Mapa (/map)", width='stretch')
                                else:
                                    # modo normal: só exibe o mapa
                                    st.image(pil_to_show, caption="Mapa (/map)", width='stretch')

                                # Se existir waypoint temporário, permite ajustar yaw
                                if st.session_state['pending_goal'] is not None:
                                    pg = st.session_state['pending_goal']
                                    st.info(f"Waypoint temporário: X={pg['x']:.3f} m, Y={pg['y']:.3f} m (frame 'map')")
                                    yaw_default = float(st.session_state.get('wp_yaw_deg', math.degrees(yaw_robot)))
                                    st.session_state['wp_yaw_deg'] = st.number_input(
                                        "Yaw do waypoint (graus)",
                                        value=yaw_default, step=5.0, format="%.1f",
                                        key="wp_yaw_deg"
                                    )

                                # idade do mapa
                                if last_update:
                                    age = time.time() - last_update
                                    st.caption(f"Última atualização: {age:.1f}s atrás")
                            else:
                                st.warning("Tamanho dos dados do mapa inconsistente")
                        except Exception as e:
                            st.error(f"Erro ao processar mapa: {e}")
                    else:
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
                    px = _fv(pos, 'x'); py = _fv(pos, 'y'); pz = _fv(pos, 'z')
                    ox = _fv(ori, 'x'); oy = _fv(ori, 'y'); oz = _fv(ori, 'z'); ow = _fv(ori, 'w', 1.0)

                    st.markdown("**Translation**")
                    st.text(f"X: {repr(px)}")
                    st.text(f"Y: {repr(py)}")
                    st.text(f"Z: {repr(pz)}")

                    st.markdown("**Rotation**")
                    st.text(f"x: {repr(ox)}")
                    st.text(f"y: {repr(oy)}")
                    st.text(f"z: {repr(oz)}")
                    st.text(f"w: {repr(ow)}")

                    # --- Waypoint temporário (abaixo do Rotation) ---
                    pg = st.session_state.get('pending_goal')
                    st.markdown("**Waypoint temporário**")
                    if pg:
                        try:
                            st.text(f"X: {pg['x']:.3f}")
                            st.text(f"Y: {pg['y']:.3f}")
                        except Exception:
                            st.text("X: —")
                            st.text("Y: —")
                    else:
                        st.text("X: —")
                        st.text("Y: —")
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