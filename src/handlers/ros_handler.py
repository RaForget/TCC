from dotenv import load_dotenv
load_dotenv()

import os
import threading
import time
import json

# roslibpy é usado para conectar ao rosbridge
import roslibpy

# ---------------- Toggle de POST ---------------------------------
POST_ENABLED = False

def enable_post():
    global POST_ENABLED
    POST_ENABLED = True

def disable_post():
    global POST_ENABLED
    POST_ENABLED = False

def is_post_enabled():
    return POST_ENABLED

# ---------------- RobotState -------------------------------------
class RobotState:
    def __init__(self):
        self.linear_velocity = 0.0
        self.angular_velocity = 0.0
        self.position = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.orientation = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 1.0}
        self._lock = threading.Lock()
        self.last_update = time.time()

    def update_velocity(self, linear, angular):
        with self._lock:
            try:
                self.linear_velocity = float(linear)
            except Exception:
                pass
            try:
                self.angular_velocity = float(angular)
            except Exception:
                pass
            self.last_update = time.time()

    def get_velocity(self):
        with self._lock:
            return self.linear_velocity, self.angular_velocity

    def update_pose(self, position_dict=None, orientation_dict=None):
        with self._lock:
            if position_dict and isinstance(position_dict, dict):
                for k in ('x','y','z'):
                    if k in position_dict:
                        try:
                            self.position[k] = float(position_dict[k])
                        except Exception:
                            pass
            if orientation_dict and isinstance(orientation_dict, dict):
                for k in ('x','y','z','w'):
                    if k in orientation_dict:
                        try:
                            self.orientation[k] = float(orientation_dict[k])
                        except Exception:
                            pass
            self.last_update = time.time()

    def get_pose(self):
        with self._lock:
            return dict(self.position), dict(self.orientation)

# ---------------- Callbacks --------------------------------------
def tf_callback(message, robot_state):
    """
    Lê tf2_msgs/TFMessage com transform.transform.translation{ x,y,z } e
    transform.transform.rotation{ x,y,z,w }.
    Atualiza robot_state quando houver um transform entre 'map' e qualquer um dos
    frames úteis ('base_link','base_footprint','base','odom').
    Aceita tanto map->odom quanto map->base_link (ou a ordem inversa).
    """
    try:
        transforms = message.get('transforms') or message.get('transform') or []
        if isinstance(transforms, dict):
            transforms = [transforms]
        for t in transforms:
            header = t.get('header', {}) or {}
            frame = header.get('frame_id') or header.get('frame') or t.get('frame_id') or t.get('frame')
            child = t.get('child_frame_id') or t.get('child') or t.get('child_frame') or t.get('child_frame_id')

            transform_obj = t.get('transform') or {}
            translation = transform_obj.get('translation') or {}
            rotation = transform_obj.get('rotation') or {}

            # converte valores simples
            try:
                pos = {'x': float(translation.get('x', 0.0)),
                       'y': float(translation.get('y', 0.0)),
                       'z': float(translation.get('z', 0.0))}
            except Exception:
                pos = {k: translation.get(k, 0.0) for k in ('x','y','z')}
            try:
                ori = {'x': float(rotation.get('x', 0.0)),
                       'y': float(rotation.get('y', 0.0)),
                       'z': float(rotation.get('z', 0.0)),
                       'w': float(rotation.get('w', 1.0))}
            except Exception:
                ori = {k: rotation.get(k, 0.0) for k in ('x','y','z','w')}

            # frames que consideramos relevantes para mostrar a pose
            useful_children = ('base_link','base_footprint','base','odom')

            # Se houver transform entre map <-> (base_link|odom|...), atualiza pose
            if (frame in ('map','/map','world') and child in useful_children) or \
               (child in ('map','/map','world') and frame in useful_children):
                robot_state.update_pose(position_dict=pos, orientation_dict=ori)
                return

            # Fallback: odom <-> base_link também pode representar pose útil
            if (frame in ('odom','/odom') and child in ('base_link','base_footprint','base')) or \
               (child in ('odom','/odom') and frame in ('base_link','base_footprint','base')):
                robot_state.update_pose(position_dict=pos, orientation_dict=ori)
                return
    except Exception:
        pass

def odom_callback(message, robot_state):
    """
    Trata nav_msgs/Odometry (se disponível) como fallback.
    """
    try:
        pose = None
        if isinstance(message.get('pose'), dict) and 'pose' in message['pose']:
            pose = message['pose']['pose']
        elif isinstance(message.get('pose'), dict):
            pose = message.get('pose')
        elif isinstance(message.get('msg'), dict) and isinstance(message['msg'].get('pose'), dict):
            pose = message['msg']['pose'].get('pose') or message['msg']['pose']
        if pose and isinstance(pose, dict):
            pos = pose.get('position', {}) or {}
            ori = pose.get('orientation', {}) or {}
            robot_state.update_pose(position_dict=pos, orientation_dict=ori)
    except Exception:
        pass

def cmd_vel_callback(message, robot_state):
    """
    Processa mensagens do tópico /cmd_vel (geometry_msgs/Twist).
    Atualiza velocidades no RobotState de forma thread-safe.
    """
    try:
        # extrai mensagem do wrapper do rosbridge se necessário
        msg = message.get('msg', message) if isinstance(message, dict) else message
        
        # obtém campos linear/angular
        linear_msg = msg.get('linear', {})
        angular_msg = msg.get('angular', {})
        
        # extrai velocidades (x linear, z angular)
        try:
            linear = float(linear_msg.get('x', 0.0))
        except (ValueError, TypeError):
            linear = 0.0
            
        try:
            angular = float(angular_msg.get('z', 0.0))
        except (ValueError, TypeError):
            angular = 0.0
            
        # atualiza estado do robô thread-safe
        robot_state.update_velocity(linear, angular)
    except Exception:
        pass

# ---------------- MapState -------------------------------------
class MapState:
    def __init__(self):
        self._lock = threading.Lock()
        self.last_map = None
        self.last_update = 0.0

    def update_map(self, msg):
        """
        Espera estrutura de OccupancyGrid via rosbridge:
        message -> {'data': [...], 'info': {'width':N, 'height':M, 'resolution':r, 'origin': {'position':{'x':..,'y':..}}}}
        tolerante a variações no encapsulamento.
        """
        try:
            # normalize message shape
            if isinstance(msg, dict) and 'msg' in msg and isinstance(msg['msg'], dict):
                payload = msg['msg']
            else:
                payload = msg
            data = payload.get('data') or payload.get('map') or payload.get('occupancy') or []
            info = payload.get('info') or payload.get('map', {}).get('info') or payload.get('meta') or {}
            # try to coerce to basic dict
            info_simple = {}
            if isinstance(info, dict):
                info_simple = info
            with self._lock:
                self.last_map = {'data': data, 'info': info_simple}
                self.last_update = time.time()
        except Exception:
            pass

    def get_map(self):
        with self._lock:
            return dict(self.last_map) if self.last_map is not None else None

# ---------------- Initialization / Subscriptions ------------------
def initialize_ros_connection(host=None, port=9090, timeout=5):
    """
    Inicializa conexão ROS e subscreve em todos os tópicos necessários.
    Retorna: (robot_state, map_state, client, cmd_vel_pub)
    """
    host = host or os.getenv('ROSBRIDGE_HOST', 'localhost')
    port = int(port or os.getenv('ROSBRIDGE_PORT', 9090))
    client = roslibpy.Ros(host=host, port=port)
    client.run()

    # aguarda conexão até timeout
    start = time.time()
    while not getattr(client, 'is_connected', False) and (time.time() - start) < float(timeout):
        time.sleep(0.02)

    if not getattr(client, 'is_connected', False):
        return None, None, client, None

    # Inicializa estados e lista de tópicos
    robot_state = RobotState()
    map_state = MapState()
    _subs = []  # guarda referências para evitar garbage collection

    # 1. Subscrição ao /tf para atualizações de posição
    try:
        tf_sub = roslibpy.Topic(client, '/tf', 'tf2_msgs/TFMessage')
        tf_sub.subscribe(lambda msg: tf_callback(msg, robot_state))
        _subs.append(tf_sub)
    except Exception as e:
        print(f"Erro ao subscrever /tf: {e}")

    # 2. Subscrição ao /cmd_vel para velocidades
    try:
        cmd_vel_sub = roslibpy.Topic(client, '/cmd_vel', 'geometry_msgs/Twist')
        cmd_vel_sub.subscribe(lambda msg: cmd_vel_callback(msg, robot_state))
        _subs.append(cmd_vel_sub)
    except Exception as e:
        print(f"Erro ao subscrever /cmd_vel: {e}")

    # 3. Subscrição ao /map para atualizações do mapa
    try:
        map_sub = roslibpy.Topic(client, '/map', 'nav_msgs/OccupancyGrid')
        map_sub.subscribe(lambda msg: map_state.update_map(msg))
        _subs.append(map_sub)
    except Exception as e:
        print(f"Erro ao subscrever /map: {e}")

    # Cria publisher para /cmd_vel
    try:
        cmd_vel_pub = roslibpy.Topic(client, '/cmd_vel', 'geometry_msgs/Twist')
        _subs.append(cmd_vel_pub)
    except Exception:
        cmd_vel_pub = None

    # Guarda referências em ambos os estados
    try:
        setattr(robot_state, '_ros_topics', _subs)
        setattr(map_state, '_ros_topics', _subs)
    except Exception:
        pass

    return robot_state, map_state, client, cmd_vel_pub

# ---------------- Publisher helper (stub) -------------------------
def send_velocity_command(linear, angular, cmd_vel_pub=None):
    """
    Publica geometry_msgs/Twist via cmd_vel_pub (roslibpy.Topic).
    Se cmd_vel_pub for None, não faz nada e retorna False.
    """
    try:
        if cmd_vel_pub is None:
            return False
        msg = {
            'linear': {'x': float(linear), 'y': 0.0, 'z': 0.0},
            'angular': {'x': 0.0, 'y': 0.0, 'z': float(angular)}
        }
        cmd_vel_pub.publish(roslibpy.Message(msg))
        return True
    except Exception:
        return False

