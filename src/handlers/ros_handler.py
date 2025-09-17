import threading
import roslibpy
import os
import time
from dotenv import load_dotenv 

# Carrega variáveis de ambiente
load_dotenv()

# Classe para armazenar o estado do robô de forma segura entre as threads
class RobotState:
    def __init__(self):
        self.linear_velocity = 0.0
        self.angular_velocity = 0.0
        self._lock = threading.Lock()

    def update_velocity(self, linear, angular):
        with self._lock:
            self.linear_velocity = linear
            self.angular_velocity = angular

    def get_velocity(self):
        with self._lock:
            return self.linear_velocity, self.angular_velocity

# Função "callback"
def cmd_vel_callback(message, robot_state):
    linear = message['linear']['x']
    angular = message['angular']['z']
    robot_state.update_velocity(linear, angular)
    print(f"Dados recebidos: Linear={linear:.4f}, Angular={angular:.4f}")

# Função para iniciar a conexão
def initialize_ros_connection():
    # IMPORTANTE: Coloque o IP da sua VM ROS aqui!
    # ROS_IP = '191.52.193.86' 
    ROS_IP = os.getenv('ROS_IP', '192.168.1.11') # Valor padrão caso a variável não exista

    try:
        robot_state = RobotState()
        client = roslibpy.Ros(host=ROS_IP, port=9090)
        
        print("Tentando conectar ao ROSBridge em {ROS_IP}:9090...")
        client.run()

        timeout = 10  # segundos
        start_time = time.time()
        while not client.is_connected and time.time() - start_time < timeout:
            time.sleep(0.1)

        if client.is_connected:
            print("Conectado ao ROS com sucesso!")
            cmd_vel_subscriber = roslibpy.Topic(client, '/cmd_vel', 'geometry_msgs/Twist')
            cmd_vel_subscriber.subscribe(lambda message: cmd_vel_callback(message, robot_state))
            return robot_state, client
        else:
            print(f"Falha ao conectar com o ROS em {timeout} segundos.")
            client.terminate()
            return None, None
            
    except Exception as e:
        print(f"Erro ao inicializar conexão ROS: {e}")
        return None, None
    
# ------------------------------------- POST -------------------------------------

def send_velocity_command(publisher, linear_x=0.0, angular_z=0.0):
    """
    Cria e publica uma mensagem Twist no tópico /cmd_vel.
    Esta função centraliza a lógica de envio de comandos.
    """
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
    print(f"Comando enviado: Linear X={linear_x}, Angular Z={angular_z}")
