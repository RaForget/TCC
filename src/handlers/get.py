import roslibpy
import time
import threading

# Cria uma classe para armazenar o estado do robô.
# Este é o nosso "quadro de avisos".
class RobotState:
    def __init__(self):
        self.linear_velocity = 0.0
        self.angular_velocity = 0.0
        # Usamos um Lock para garantir que a escrita e leitura sejam seguras entre threads
        self._lock = threading.Lock()

    def update_velocity(self, linear, angular):
        # Travamos o acesso para garantir que a interface não leia enquanto estamos escrevendo
        with self._lock:
            self.linear_velocity = linear
            self.angular_velocity = angular

    def get_velocity(self):
        # Travamos o acesso para garantir que o callback não escreva enquanto estamos lendo
        with self._lock:
            return self.linear_velocity, self.angular_velocity

def cmd_vel_callback(message, robot_state):
    # Extrai os dados do cmd_vel
    linear_velocity = message['linear']['x']
    angular_velocity = message['angular']['z']
    robot_state.update_velocity(linear_velocity, angular_velocity)
    print(f"Linear= {linear_velocity} | Angular= {angular_velocity}")

# Esta função simula a sua interface rodando em paralelo
def interface_loop(robot_state):
    while True:
        # A interface "lê o quadro de avisos" para obter os dados mais recentes
        linear, angular = robot_state.get_velocity()
        
        # Aqui você faria a mágica da sua interface (atualizar um label, um gráfico, etc.)
        # Por enquanto, vamos apenas imprimir a cada segundo.
        print("--------------------------")
        print(f"INTERFACE LENDO O ESTADO:")
        print(f"  Velocidade Linear: {linear:.4f}")
        print(f"  Velocidade Angular: {angular:.4f}")
        print("--------------------------")
        
        time.sleep(1) # Roda a 1Hz para não poluir o terminal

def main():
    # Configura a conexão WebSocket com o ROSBridge
    rosbridge_ws_url = '192.168.1.11'  # IP do dispositivo ROS

    robot_state = RobotState()

    print(f"Tentando conectar a {rosbridge_ws_url}:9090...")
    
    try:
        client = roslibpy.Ros(host=rosbridge_ws_url, port=9090)
        client.run(timeout=10)  # Tenta iniciar a thread de comunicação do ROS em background por 10s
        
        if client.is_connected:
            print('Conectado ao ROS!')
            
            # Subscrevendo ao tópico /cmd_vel
            cmd_vel_subscriber = roslibpy.Topic(client, '/cmd_vel', 'geometry_msgs/Twist')

            # Conectando o callback para receber mensagens
            cmd_vel_subscriber.subscribe(lambda message: cmd_vel_callback(message, robot_state))

            # Mantém o cliente em execução para ouvir as mensagens
            try:
                while True:
                    pass
            except KeyboardInterrupt:
                client.terminate()

        else:
            print('Falha na conexão!')
            
    except Exception as e:
        print(f"Erro de conexão: {e}")
        return

if __name__ == "__main__":
    main()
