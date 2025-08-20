import roslibpy

def cmd_vel_callback(message):
    # Extrai os dados do cmd_vel
    linear_velocity = message['linear']['x']
    angular_velocity = message['angular']['z']
    print(f"Received cmd_vel: Linear Velocity: {linear_velocity}, Angular Velocity: {angular_velocity}")

def main():
    # Configura a conexão WebSocket com o ROSBridge
    # rosbridge_ws_url = '192.168.137.150'  # IP do dispositivo ROS - (IP da JETSON)
    rosbridge_ws_url = '172.31.159.255'  # IP do dispositivo ROS


    client = roslibpy.Ros(host=rosbridge_ws_url, port=9090)

    # Conecta ao ROS
    client.run()

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

if __name__ == "__main__":
    main()
