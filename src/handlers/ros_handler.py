from dotenv import load_dotenv
load_dotenv()

import os
import threading
import time
import json
import math, time

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
            _update_tf_and_pose(robot_state, frame, child, translation, rotation)
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

def _norm_frame(name):
    return str(name).lstrip('/') if name else ''

def _quat_multiply(q1, q2):
    x1,y1,z1,w1 = q1
    x2,y2,z2,w2 = q2
    return (
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2,
        w1*w2 - x1*x2 - y1*y2 - z1*z2
    )

def _yaw_from_quat(q):
    x,y,z,w = q
    return math.atan2(2.0*(w*z + x*y), 1.0 - 2.0*(y*y + z*z))

def _rotate_xy(x, y, yaw):
    cy, sy = math.cos(yaw), math.sin(yaw)
    return (cy*x - sy*y, sy*x + cy*y)

def _ensure_tf_store(robot_state):
    if not hasattr(robot_state, '_tf_store'):
        robot_state._tf_store = {}
    return robot_state._tf_store

def _update_tf_and_pose(robot_state, frame, child, translation, rotation):
    tf_store = _ensure_tf_store(robot_state)
    f = _norm_frame(frame)
    c = _norm_frame(child)
    trans = {
        'x': float(translation.get('x', 0.0)),
        'y': float(translation.get('y', 0.0)),
        'z': float(translation.get('z', 0.0)),
    }
    rot = {
        'x': float(rotation.get('x', 0.0)),
        'y': float(rotation.get('y', 0.0)),
        'z': float(rotation.get('z', 0.0)),
        'w': float(rotation.get('w', 1.0)),
    }
    tf_store[(f, c)] = {'t': trans, 'r': rot, 'ts': time.time()}

    def get(fr, ch):
        return tf_store.get((_norm_frame(fr), _norm_frame(ch)))

    # 1) direto: map->base_link
    direct = get('map', 'base_link') or get('map', 'base_footprint') or get('world', 'base_link')
    if direct:
        robot_state.update_pose(position_dict=direct['t'], orientation_dict=direct['r'])
        return

    # 2) composição: map->odom + odom->base_link
    t1 = get('map', 'odom') or get('world', 'odom')
    t2 = get('odom', 'base_link') or get('odom', 'base_footprint') or get('odom', 'base')
    if t1 and t2:
        x1,y1,z1 = t1['t']['x'], t1['t']['y'], t1['t']['z']
        x2,y2,z2 = t2['t']['x'], t2['t']['y'], t2['t']['z']
        q1 = (t1['r']['x'], t1['r']['y'], t1['r']['z'], t1['r']['w'])
        q2 = (t2['r']['x'], t2['r']['y'], t2['r']['z'], t2['r']['w'])
        yaw1 = _yaw_from_quat(q1)
        rx, ry = _rotate_xy(x2, y2, yaw1)
        pos = {'x': x1 + rx, 'y': y1 + ry, 'z': z1 + z2}
        q = _quat_multiply(q1, q2)
        ori = {'x': q[0], 'y': q[1], 'z': q[2], 'w': q[3]}
        robot_state.update_pose(position_dict=pos, orientation_dict=ori)
        return

    # 3) fallback: odom->base_link (pose no frame odom)
    if t2:
        robot_state.update_pose(position_dict=t2['t'], orientation_dict=t2['r'])

# ...existing code...

