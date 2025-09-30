import sys
import time
import roslibpy
from pprint import pprint

def print_tf_message(msg):
    transforms = msg.get('transforms') or msg.get('transform') or []
    if isinstance(transforms, dict):
        transforms = [transforms]
    for t in transforms:
        header = t.get('header', {}) or {}
        frame = header.get('frame_id') or header.get('frame') or t.get('frame_id')
        child = t.get('child_frame_id') or t.get('child') or t.get('child_frame')
        transform = t.get('transform') or {}
        translation = transform.get('translation') or t.get('translation') or {}
        rotation = transform.get('rotation') or t.get('rotation') or {}
        print("---- transform ----")
        print("frame:", frame, " child:", child)
        print("translation:")
        print("  x:", translation.get('x'))
        print("  y:", translation.get('y'))
        print("  z:", translation.get('z'))
        print("rotation:")
        print("  x:", rotation.get('x'))
        print("  y:", rotation.get('y'))
        print("  z:", rotation.get('z'))
        print("  w:", rotation.get('w'))
    sys.stdout.flush()

def main(host='localhost', port=9090, duration=None):
    client = roslibpy.Ros(host=host, port=port)
    client.run()
    start = time.time()
    while not getattr(client, 'is_connected', False) and (time.time() - start) < 5:
        time.sleep(0.05)
    if not getattr(client, 'is_connected', False):
        print("Erro: não conseguiu conectar ao rosbridge:", host, port)
        return
    print("Conectado ao rosbridge:", host, port)
    tf_topic = roslibpy.Topic(client, '/tf', 'tf2_msgs/TFMessage')
    tf_topic.subscribe(print_tf_message)
    print("Inscrito em /tf — esperando mensagens (Ctrl+C para sair)...")
    try:
        t0 = time.time()
        while True:
            if duration and (time.time() - t0) > duration:
                break
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            tf_topic.unsubscribe()
        except Exception:
            pass
        client.terminate()
        print("Encerrado.")

if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else '192.168.1.11'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 9090
    dur = int(sys.argv[3]) if len(sys.argv) > 3 else None
    main(host=host, port=port, duration=dur)