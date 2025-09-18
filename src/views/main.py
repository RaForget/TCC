# Para rodar o app, use o comando: python -m streamlit run .\src\views\main.py
import streamlit as st
import sys
from pathlib import Path
import time

# Adiciona o diretório raiz ao PYTHONPATH
root_dir = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, root_dir)

# Imports absolutos
from src.handlers.ros_handler import initialize_ros_connection#, send_velocity_command
from src.views.parametrizacao import show_parametrizacao
from src.views.controles import show_controles

# Configuração da página com sidebar inicial expandida
st.set_page_config(page_title="Interface de Controle")

def main():

    if 'ros_client' not in st.session_state:
        with st.spinner('Conectando ao robô...'):
            st.session_state.robot_state, st.session_state.ros_client, st.session_state.cmd_vel_publisher = initialize_ros_connection()

    st.sidebar.title("Configurações")
    
    # Inicializa o estado do interruptor como True
    if 'auto_update_enabled' not in st.session_state:
        st.session_state.auto_update_enabled = True

    # Cria o widget de toggle e o vincula à variável da sessão
    st.session_state.auto_update_enabled = st.sidebar.toggle(
        "Habilitar atualização em tempo real", 
        value=st.session_state.auto_update_enabled,
        help="Quando ativado, os dados da interface são atualizados automaticamente."
    )
    
    st.sidebar.title("Navegação")
    # Menu de navegação
    menu = st.sidebar.selectbox(
        "Telas",
        ["Visualização", "Parametrização", "Controles"]
    )

    if menu == "Visualização":
        st.header("Visualização")
        
        col1, col2 = st.columns(2)

        with col1:
        # HTML e CSS para redimensionar imagens
            try:
                image_path = Path(__file__).parent.parent.parent / "assets" / "Simulacao.png"
                st.image(str(image_path), use_container_width=True)
            except Exception as e:
                st.error(f"Erro ao carregar a imagem: {e}")
                
        with col2:

            robot_state = st.session_state.get('robot_state', None)
            ros_client = st.session_state.get('ros_client', None)

            # Verifica se a conexão está ativa para decidir o que mostrar
            if robot_state and ros_client and ros_client.is_connected:
                # Se ONLINE, busca os dados em tempo real do objeto de estado
                linear, angular = robot_state.get_velocity()

                st.success("Online")
                st.metric(label="Velocidade Linear (m/s)", value=f"{linear:.4f}")
                st.metric(label="Velocidade Angular (rad/s)", value=f"{angular:.4f}")
            else:
                # Se OFFLINE, mostra os valores padrão
                st.error("Offline")
                st.metric(label="Velocidade Linear (m/s)", value="0.0")
                st.metric(label="Velocidade Angular (rad/s)", value="0.0")

# ----------------------------------------- Parametrização ------------------------------------------------        

    elif menu == "Parametrização":
        show_parametrizacao()

# ----------------------------------------- Controles ------------------------------------------------        

    elif menu == "Controles":
        show_controles()

if __name__ == "__main__":
    main()

    if st.session_state.get('auto_update_enabled', False):
        # Força a página a recarregar e atualizar os dados a cada meio segundo.
        try:
            time.sleep(0.5)
            st.rerun()
        except Exception as e:
            # Evita erros se a conexão for fechada abruptamente
            st.stop()