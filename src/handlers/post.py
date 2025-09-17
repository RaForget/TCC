import roslibpy
import time

# Conecte-se ao servidor rosbridge
client = roslibpy.Ros(host='192.168.1.11', port=9090)
client.run()

if client.is_connected:
    print('Conectado ao ROS via rosbridge!')

    # Cria um tópico /cmd_vel com tipo Twist
    cmd_vel_publisher = roslibpy.Topic(client, '/cmd_vel', 'geometry_msgs/Twist')

    # Define velocidades linear e angular
    linear_vel = 0.18421052631578947
    angular_vel = 0.1578947368421052

    # Cria a mensagem Twist
    twist = {
        'linear': {'x': linear_vel, 'y': 0.0, 'z': 0.0},
        'angular': {'x': 0.0, 'y': 0.0, 'z': angular_vel}
    }

    print(f'Received cmd_vel: Linear Velocity: {linear_vel}, Angular Velocity: {angular_vel}')
    
    while client.is_connected:
        cmd_vel_publisher.publish(twist)
        time.sleep(1)

    cmd_vel_publisher.unadvertise()
    client.terminate()
else:
    print('Falha ao conectar ao ROSBridge.')
