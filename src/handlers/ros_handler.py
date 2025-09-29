import threading
import os
import roslibpy
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()


# ---------------- Toggle de POST ---------------------------------
# Variável global que controla se a função de POST é executada
# Padrão: desabilitado para evitar envios acidentais ao iniciar a interface
POST_ENABLED = False

def enable_post():
    """Habilita envios de POST (publish) para o ROS."""
    global POST_ENABLED
    POST_ENABLED = True
    print("POSTs habilitados.")

def disable_post():
    """Desabilita envios de POST (publish) para o ROS."""
    global POST_ENABLED
    POST_ENABLED = False
    print("POSTs desabilitados.")

def is_post_enabled():
    """Retorna True se POSTs estiverem habilitados."""
    return POST_ENABLED

# Classe para armazenar o estado do robô de forma segura entre as threads
class RobotState:
    def __init__(self):
        self.linear_velocity = 0.0
        self.angular_velocity = 0.0
        # pose: position (x,y,z) e orientation (x,y,z,w)
        self.position = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.orientation = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 1.0}
        self._lock = threading.Lock()

    def update_velocity(self, linear, angular):
        with self._lock:
            self.linear_velocity = linear
            self.angular_velocity = angular

    def get_velocity(self):
        with self._lock:
            return self.linear_velocity, self.angular_velocity

    def update_pose(self, position_dict=None, orientation_dict=None, *, x=None, y=None, z=None, ox=None, oy=None, oz=None, ow=None):
        """
        Atualiza a pose. Aceita dicionários (position_dict, orientation_dict) ou valores individuais.
        """
        with self._lock:
            if position_dict:
                for k in ('x','y','z'):
                    if k in position_dict:
                        self.position[k] = float(position_dict[k])
            else:
                if x is not None: self.position['x'] = float(x)
                if y is not None: self.position['y'] = float(y)
                if z is not None: self.position['z'] = float(z)

            if orientation_dict:
                for k in ('x','y','z','w'):
                    if k in orientation_dict:
                        self.orientation[k] = float(orientation_dict[k])
            else:
                if ox is not None: self.orientation['x'] = float(ox)
                if oy is not None: self.orientation['y'] = float(oy)
                if oz is not None: self.orientation['z'] = float(oz)
                if ow is not None: self.orientation['w'] = float(ow)

    def get_pose(self):
        with self._lock:
            return dict(self.position), dict(self.orientation)


# Estado do mapa (armazena a última mensagem recebida)
class MapState:
    def __init__(self):
        self.last_map = None
        self._lock = threading.Lock()

    def update_map(self, map_msg):
        with self._lock:
            self.last_map = map_msg

    def get_map(self):
        with self._lock:
            return self.last_map

def cmd_vel_callback(message, robot_state):
    try:
        linear = message.get('linear', {}).get('x', 0.0)
        angular = message.get('angular', {}).get('z', 0.0)
        robot_state.update_velocity(linear, angular)
    except Exception:
        pass

def map_callback(message, map_state):
    # Recebe nav_msgs/OccupancyGrid (ou outro formato) e guarda a mensagem raw
    map_state.update_map(message)

def pose_callback(message, robot_state):
    """
    Extrai position e orientation de mensagens no formato:
    - geometry_msgs/Pose: {'position':{...}, 'orientation':{...}}
    - geometry_msgs/PoseStamped: {'pose': {'pose': {...}}}
    - ou uma forma direta {'position': {...}, 'orientation': {...}}
    """
    try:
        pos = None
        ori = None

        # PoseStamped?
        if 'pose' in message and isinstance(message['pose'], dict):
            inner = message['pose']
            # pode ser PoseStamped (pose -> pose) ou Pose (pose)
            if 'pose' in inner and isinstance(inner['pose'], dict):
                payload = inner['pose']
                pos = payload.get('position')
                ori = payload.get('orientation')
            else:
                # message['pose'] já contém position/orientation
                pos = inner.get('position')
                ori = inner.get('orientation')
        else:
            # Mensagem direta
            pos = message.get('position') or message.get('pos') or None
            ori = message.get('orientation') or message.get('orient') or None

        # Se ainda None, tenta extrair campos diretamente
        if pos is None and any(k in message for k in ('x','y','z')):
            pos = {k: message.get(k) for k in ('x','y','z')}

        if pos:
            robot_state.update_pose(position_dict=pos)
        if ori:
            robot_state.update_pose(orientation_dict=ori)
    except Exception:
        pass

# nova callback para PoseArray
def posearray_callback(message, robot_state):
    """
    Trata geometry_msgs/PoseArray: {'poses': [ {position:{}, orientation:{}}, ... ]}
    Pega a primeira pose (ou altere para escolher outra) e atualiza robot_state.
    """
    try:
        poses = message.get('poses') or []
        if not poses:
            return
        first = poses[0]
        pos = first.get('position')
        ori = first.get('orientation')
        if pos:
            robot_state.update_pose(position_dict=pos)
        if ori:
            robot_state.update_pose(orientation_dict=ori)
    except Exception:
        pass

def initialize_ros_connection(host=None, port=9090, timeout=5):
    """
    Conecta ao rosbridge e cria publishers/subscribers.
    Retorna: (robot_state, map_state, client, cmd_vel_publisher)
    """
    host = host or os.getenv('ROSBRIDGE_HOST', '192.168.1.11')
    port = int(os.getenv('ROSBRIDGE_PORT', port))

    client = roslibpy.Ros(host=host, port=port)
    client.run(timeout=timeout)

    robot_state = RobotState()
    map_state = MapState()

    if client.is_connected:
        # Publisher (se você precisar enviar comandos)
        cmd_vel_pub = roslibpy.Topic(client, '/cmd_vel', 'geometry_msgs/Twist')

        # Subscribers
        cmd_vel_sub = roslibpy.Topic(client, '/cmd_vel', 'geometry_msgs/Twist')
        cmd_vel_sub.subscribe(lambda msg: cmd_vel_callback(msg, robot_state))

        # Assumimos que /map é nav_msgs/OccupancyGrid; ajuste se for outro tipo
        map_sub = roslibpy.Topic(client, '/map', 'nav_msgs/OccupancyGrid')
        map_sub.subscribe(lambda msg: map_callback(msg, map_state))

        # Subscrição para /pose_info (tenta vários tipos)
        try:
            # Assina explicitamente PoseArray (este é o tipo correto no seu caso)
            posearray_sub = roslibpy.Topic(client, '/pose_info', 'geometry_msgs/PoseArray')
            posearray_sub.subscribe(lambda msg: posearray_callback(msg, robot_state))
        except Exception:
            pass

        # mantém as tentativas anteriores (Pose / PoseStamped) também
        try:
            pose_sub = roslibpy.Topic(client, '/pose_info', 'geometry_msgs/Pose')
            pose_sub.subscribe(lambda msg: pose_callback(msg, robot_state))
        except Exception:
            try:
                pose_sub = roslibpy.Topic(client, '/pose_info', 'geometry_msgs/PoseStamped')
                pose_sub.subscribe(lambda msg: pose_callback(msg, robot_state))
            except Exception:
                pass

        return robot_state, map_state, client, cmd_vel_pub
    else:
        # falha na conexão
        return None, None, None, None

def send_velocity_command(publisher, linear_x=0.0, angular_z=0.0):
    """
    Cria e publica uma mensagem Twist no tópico /cmd_vel.
    Esta função centraliza a lógica de envio de comandos.
    """
    # Verifica se envio de POSTs está habilitado
    try:
        if not is_post_enabled():
            print("POSTs desabilitados — comando não será enviado.")
            return
    except NameError:
        # Caso as funções de toggle não existam por algum motivo, continua o comportamento padrão
        pass

    if not publisher:
        print("Aviso: Tentativa de publicar sem um publicador inicializado.")
        return
    
    # Cria a mensagem no formato que o ROS espera
    twist = roslibpy.Message({
        'linear': {
            'x': linear_x,
            'y': 0.0,
            'z': 0.0
        },
        'angular': {
            'x': 0.0,
            'y': 0.0,
            'z': angular_z
        }
    })
    
    # Publica a mensagem
    publisher.publish(twist)

__all__ = [
    'RobotState',
    'MapState',
    'initialize_ros_connection',
    'send_velocity_command',
    'enable_post',
    'disable_post',
    'is_post_enabled'
]

