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
from src.views.controles import show_controles

# Configuração da página com sidebar inicial expandida
st.set_page_config(page_title="Interface de Controle", layout="wide")

# Clique na imagem (para waypoint temporário)
try:
    from streamlit_image_coordinates import streamlit_image_coordinates as get_img_click
except Exception:
    get_img_click = None


def main():
    # Import dinâmico via importlib + getattr para evitar import circular
    import importlib
    ros_handler = importlib.import_module('src.handlers.ros_handler')
    initialize_ros_connection = getattr(ros_handler, 'initialize_ros_connection')

    # Sidebar: configs e toggles
    st.sidebar.title("Configurações")

    # Sidebar: host/port do rosbridge
    host = st.sidebar.text_input("ROSBridge host", value=os.getenv('ROSBRIDGE_HOST', '192.168.1.11'))
    port = int(st.sidebar.number_input("ROSBridge port", value=int(os.getenv('ROSBRIDGE_PORT', '9090')),
                                       min_value=1, max_value=65535))

    # Conexão ROS
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
        if 'cmd_vel_publisher' not in st.session_state:
            st.session_state.cmd_vel_publisher = None

    if 'auto_update_enabled' not in st.session_state:
        st.session_state.auto_update_enabled = True

    st.session_state.auto_update_enabled = st.sidebar.toggle(
        "Habilitar atualização em tempo real",
        value=st.session_state.auto_update_enabled,
        help="Quando ativado, os dados da interface são atualizados automaticamente."
    )

    # Navegação
    st.sidebar.title("Navegação")
    menu = st.sidebar.selectbox("Telas", ["Visualização", "Controles"])

    # ----------------------------------------- Visualização ------------------------------------------------
    if menu == "Visualização":
        st.header("Visualização")
        col1, col2 = st.columns([4, 2], gap="large")

        with col1:
            map_state = st.session_state.get('map_state')

            # Estado de seleção de waypoint e waypoint temporário
            if 'pending_goal' not in st.session_state:
                st.session_state['pending_goal'] = None
            if 'wp_select_mode' not in st.session_state:
                st.session_state['wp_select_mode'] = True  # ativo por padrão

            st.session_state['wp_select_mode'] = st.toggle(
                "Modo seleção de waypoint (clicar no mapa)",
                value=st.session_state['wp_select_mode']
            )

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
                                # OccupancyGrid -> imagem (flip vertical para exibição)
                                img_arr = np.where(data == -1, 127, np.where(data == 0, 255, 0)).astype(np.uint8)
                                img_arr = img_arr.reshape((height, width))
                                img_arr = np.flipud(img_arr)
                                pil_img = Image.fromarray(img_arr).convert('L')

                                # Pose do robô e parâmetros do origin
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
                                    yaw0 = math.atan2(2.0 * (ow_q * oz_q + ox_q * oy_q), 1.0 - 2.0 * (oy_q * oy_q + oz_q * oz_q))
                                except Exception:
                                    yaw0 = 0.0

                                rx = float(pos.get('x', 0.0))
                                ry = float(pos.get('y', 0.0))
                                qx = float(ori.get('x', 0.0))
                                qy = float(ori.get('y', 0.0))
                                qz = float(ori.get('z', 0.0))
                                qw = float(ori.get('w', 1.0))

                                # map->pixels (compensando rotação do origin)
                                dx = rx - ox
                                dy = ry - oy
                                if abs(yaw0) > 1e-6:
                                    cy, sy = math.cos(-yaw0), math.sin(-yaw0)
                                    mx = cy * dx - sy * dy
                                    my = sy * dx + cy * dy
                                else:
                                    mx, my = dx, dy
                                px = int(round(mx / resolution))
                                py = int(round(my / resolution))

                                # yaw do robô para desenhar seta
                                try:
                                    yaw_robot = math.atan2(2.0 * (qw * qz + qx * qy), 1.0 - 2.0 * (qy * qy + qz * qz))
                                except Exception:
                                    yaw_robot = 0.0
                                yaw_disp = yaw_robot - yaw0
                                if yaw_disp > math.pi:
                                    yaw_disp -= 2.0 * math.pi
                                if yaw_disp < -math.pi:
                                    yaw_disp += 2.0 * math.pi

                                # Desenha seta
                                def disp_y(y_pix):
                                    return (height - 1) - y_pix

                                L_pix = max(16, int(round(0.5 / max(resolution, 1e-6))))
                                base_w = max(12, int(round(L_pix * 0.65)))
                                back_off = int(round(L_pix * 0.35))
                                c = math.cos(yaw_disp)
                                s = math.sin(yaw_disp)
                                ax = px + int(round(L_pix * c))
                                ay = py + int(round(L_pix * s))
                                bx = px - int(round(back_off * c))
                                by = py - int(round(back_off * s))
                                half_w = base_w // 2
                                lx = bx + int(round(half_w * (-s)))
                                ly = by + int(round(half_w * (c)))
                                rx_ = bx - int(round(half_w * (-s)))
                                ry_ = by - int(round(half_w * (c)))
                                p_apex = (ax, disp_y(ay))
                                p_left = (lx, disp_y(ly))
                                p_right = (rx_, disp_y(ry_))

                                pil_rgb = pil_img.convert('RGB')
                                draw = ImageDraw.Draw(pil_rgb)
                                tri = [p_apex, p_right, p_left]
                                draw.polygon(tri, fill=(245, 179, 66))
                                draw.line(tri + [tri[0]], fill=(0, 0, 0), width=2)
                                pil_to_show = pil_rgb

                                # Imagem clicável para waypoint temporário
                                if st.session_state['wp_select_mode'] and get_img_click is not None:
                                    st.caption("Clique no mapa para escolher o waypoint temporário")
                                    # O componente não aceita width='stretch'
                                    click = get_img_click(pil_to_show, key="map_click_wp")

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
                                                   outline=(0, 255, 0), width=3)
                                        st.image(marked, caption="Mapa (/map)", width='stretch')

                                        # Converte para coordenadas do mapa (desfaz flip)
                                        py_pix = int(round((height - 1) - py_pix_img))
                                        mx_goal = px_pix * resolution
                                        my_goal = py_pix * resolution
                                        if abs(yaw0) > 1e-6:
                                            c0, s0 = math.cos(yaw0), math.sin(yaw0)
                                            dx_g = c0 * mx_goal - s0 * my_goal
                                            dy_g = s0 * mx_goal + c0 * my_goal
                                        else:
                                            dx_g, dy_g = mx_goal, my_goal
                                        gx = ox + dx_g
                                        gy = oy + dy_g

                                        st.session_state['pending_goal'] = {'x': gx, 'y': gy}
                                    else:
                                        # Ainda sem clique
                                        st.image(pil_to_show, caption="Mapa (/map)", width='stretch')
                                else:
                                    # Modo normal: só exibe o mapa
                                    st.image(pil_to_show, caption="Mapa (/map)", width='stretch')

                                # Removido: info do waypoint temporário no painel do mapa
                                # (as coordenadas permanecem apenas na coluna da direita)
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
                # Se ONLINE, busca os dados em tempo real
                linear, angular = robot_state.get_velocity()

                st.success("Online")
                st.metric(label="Velocidade Linear (m/s)", value=f"{linear:.4f}")
                st.metric(label="Velocidade Angular (rad/s)", value=f"{angular:.4f}")

                # Exibe pose do robô
                try:
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

                    px = _fv(pos, 'x')
                    py = _fv(pos, 'y')
                    pz = _fv(pos, 'z')
                    ox = _fv(ori, 'x')
                    oy = _fv(ori, 'y')
                    oz = _fv(ori, 'z')
                    ow = _fv(ori, 'w', 1.0)

                    st.markdown("**Translation**")
                    st.text(f"X: {repr(px)}")
                    st.text(f"Y: {repr(py)}")

                    st.markdown("**Rotation**")
                    st.text(f"z: {repr(oz)}")
                    st.text(f"w: {repr(ow)}")

                    # Waypoint temporário (abaixo do Rotation)
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

                    # Botão de envio (abaixo do Waypoint temporário)
                    if st.button("Enviar waypoint", type="primary", key="btn_send_wp_bottom"):
                        pg2 = st.session_state.get('pending_goal')
                        if not pg2:
                            st.warning("Nenhum waypoint temporário selecionado.")
                        else:
                            # Usa o yaw atual do robô
                            try:
                                yaw_rad = math.atan2(2.0 * (ow * oz + ox * oy), 1.0 - 2.0 * (oy * oy + oz * oz))
                            except Exception:
                                yaw_rad = 0.0

                            # Publica via ros_handler.publish_goal_pose, com fallback
                            publish_goal_pose = getattr(ros_handler, 'publish_goal_pose', None)
                            def _publish_goal_pose_fallback(x, y, yaw_r):
                                try:
                                    import roslibpy
                                    import time as _t
                                    client = st.session_state.get('ros_client')
                                    if not client or not getattr(client, 'is_connected', False):
                                        return False
                                    topic = roslibpy.Topic(client, '/goal_pose', 'geometry_msgs/PoseStamped')
                                    now = _t.time()
                                    sec = int(now)
                                    nsec = int((now - sec) * 1e9)
                                    qz = math.sin(yaw_r / 2.0)
                                    qw = math.cos(yaw_r / 2.0)
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
                                    ok = publish_goal_pose(pg2['x'], pg2['y'], yaw_rad,
                                                           frame_id='map', topic_name='/goal_pose',
                                                           goal_pub=getattr(st.session_state.get('robot_state', None), 'goal_pose_pub', None),
                                                           client=st.session_state.get('ros_client'))
                            except Exception:
                                ok = False
                            if not ok:
                                ok = _publish_goal_pose_fallback(pg2['x'], pg2['y'], yaw_rad)
                            if ok:
                                st.success("Waypoint publicado em /goal_pose.")
                            else:
                                st.error("Falha ao publicar em /goal_pose.")
                except Exception as e:
                    st.write("Erro ao exibir pose:", e)
            else:
                st.warning("Offline")

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
        except Exception:
            # Evita erros se a conexão for fechada abruptamente
            st.stop()