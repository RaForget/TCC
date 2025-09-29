import sys
import time
import threading
import roslibpy

def try_subscribe(host, port, timeout=10):
    client = roslibpy.Ros(host=host, port=port)
    try:
        print(f"Tentando conectar em {host}:{port} (timeout {timeout}s)...")
        client.run(timeout=timeout)
        print("is_connected:", client.is_connected)
        if not client.is_connected:
            return

        received = threading.Event()

        def make_cb(label):
            def cb(msg):
                print(f"--- Mensagem recebida ({label}) ---")
                print(msg)
                received.set()
            return cb

        # Tenta assinar como PoseStamped (comum) e Pose (caso seja direto)
        sub_ps = roslibpy.Topic(client, '/pose_info', 'geometry_msgs/PoseStamped')
        sub_p = roslibpy.Topic(client, '/pose_info', 'geometry_msgs/Pose')

        sub_ps.subscribe(make_cb('PoseStamped'))
        sub_p.subscribe(make_cb('Pose'))

        # adiciona tentativa para PoseArray
        sub_pa = roslibpy.Topic(client, '/pose_info', 'geometry_msgs/PoseArray')
        sub_pa.subscribe(make_cb('PoseArray'))
        # já tem sub_ps e sub_p — ok

        # Espera mensagem por até timeout segundos
        wait_sec = timeout
        print(f"Aguardando mensagens em /pose_info por {wait_sec}s...")
        received.wait(wait_sec)

        if not received.is_set():
            print("Nenhuma mensagem recebida em /pose_info com os tipos tentados.")
            print("- Verifique em que tópico / formato a simulação publica.")
            print("- Execute no computador da simulação: rostopic echo /pose_info")
        else:
            print("Recebido com sucesso.")

        # cleanup
        try:
            sub_ps.unsubscribe()
            sub_p.unsubscribe()
            # cleanup: unsubscribe sub_pa também
            sub_pa.unsubscribe()
        except Exception:
            pass

    except Exception as e:
        print("Erro durante teste:", e)
    finally:
        try:
            client.terminate()
        except Exception:
            pass

if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else '192.168.1.11'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 9090
    try_subscribe(host, port, timeout=12)