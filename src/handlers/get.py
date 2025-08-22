import roslibpy
import time

def cmd_vel_callback(message):
    # Extrai os dados do cmd_vel
    linear_velocity = message['linear']['x']
    angular_velocity = message['angular']['z']
    print(f"Received cmd_vel: Linear Velocity: {linear_velocity}, Angular Velocity: {angular_velocity}")

def main():
    # Configura a conexão WebSocket com o ROSBridge
    # rosbridge_ws_url = '192.168.137.150'  # IP do dispositivo ROS - (IP da JETSON)
    rosbridge_ws_url = '172.31.151.215'  # IP do dispositivo ROS

    print(f"Tentando conectar a {rosbridge_ws_url}:9090...")
    
    try:
        client = roslibpy.Ros(host=rosbridge_ws_url, port=9090)
        client.run(timeout=10)  # Timeout de 10 segundos
        
        if client.is_connected:
            print('Conectado ao ROS!')
            
            # Subscrevendo ao tópico /cmd_vel
            cmd_vel_subscriber = roslibpy.Topic(client, '/cmd_vel', 'geometry_msgs/Twist')

            # Conectando o callback para receber mensagens
            cmd_vel_subscriber.subscribe(cmd_vel_callback)

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
