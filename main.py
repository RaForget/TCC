# Para rodar o app, use o comando: streamlit run ElderlyHater.py
import streamlit as st
import base64  # Import necessário para codificar em base64

# Importar variáveis de outros arquivos via funções
from processamento import update_velocity_data, process_position_data

# from Post import post_cmd_vel --- Exemplo de importação de função para enviar comandos
# from Get import get_cmd_vel --- Exemplo de importação de função para receber comandos

# Configuração da página com sidebar inicial expandida
st.set_page_config(
    page_title="Interface de Controle"
)


def main():
    # st.title("GUI")
    
    # Menu de navegação
    menu = st.sidebar.selectbox(
        "Menu",
        ["Visualização", "Parametrização", "Controles"]
    )

    if menu == "Visualização":
        st.header("Visualização")
        
        col1, col2 = st.columns(2)

        with col1:
        # HTML e CSS para redimensionar imagens
            try:
                # Carregar imagem
                with open("Simulacao.png", "rb") as img:
                    img_bytes = img.read()
                    img_base64 = base64.b64encode(img_bytes).decode("utf-8")

                    st.markdown(
                        f"""
                        <style>
                            /* ----- Mapa ----- */
                            .map-container {{
                                position: absolute;
                                top: 0px;
                                left: 0;
                                width: 100%; /* Ocupa toda a largura da tela */
                                height: 350px;
                                z-index: 1000;
                                border: 2px solid #0000FF; /* Adiciona uma borda azul */
                            }}
                            .map-container img {{
                                width: 100%;
                                height: 100%;
                                object-fit: cover; /* Garante que a imagem preencha a div */
                                cursor: pointer; /* Mostra o cursor de clique */
                            }}
                        </style>
                        <div class="map-container">
                            <a href="https://example.com" target="_blank">
                            <img src="data:image/png;base64,{img_base64}">
                            </a>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
            except FileNotFoundError:
                st.error("O arquivo de vídeo não foi encontrado. Verifique o caminho e tente novamente.")
                
        with col2:
            st.markdown(
                """
                <style>
                .centered-text {
                    text-align: center;
                    margin-bottom: 20px;  /* Espaçamento entre os blocos de texto */
                }
                .centered-text strong {
                    font-size: 28px;  /* Tamanho da fonte do texto em negrito */
                    margin-top: 13px;  /* Espaçamento acima do texto em negrito */
                    display: block;  /* Faz funcionar o margin */
                }
                .centered-text:not(:has(strong)) {
                    font-size: 20px;  /* Tamanho da fonte do texto normal */
                    margin-bottom: 80px;  /* Espaçamento entre os blocos de texto */
                </style>
                """, 
                unsafe_allow_html=True
            )
    
            # Atualiza dados de velocidade
            velocidade = update_velocity_data()
            if velocidade:
                st.markdown("<p class='centered-text'><strong>Velocidade</strong></p>", 
                          unsafe_allow_html=True)
                st.markdown(
                    f"<p class='centered-text'>Linear: {velocidade['Linear']} | Angular: {velocidade['Angular']}</p>",
                    unsafe_allow_html=True
                )
            
            # Atualiza dados de posição
            #posicao = process_position_data()
            #st.markdown("<p class='centered-text'><strong>Posição</strong></p>", 
            #          unsafe_allow_html=True)
            #st.markdown(
            #    f"<p class='centered-text'>X: {posicao['X']} | Y: {posicao['Y']} | Z: {posicao['Z']}</p>",
            #    unsafe_allow_html=True
            #)

# ----------------------------------------- Parametrização ------------------------------------------------        

    elif menu == "Parametrização":
        st.header("Parametrização")

        # Inicializa valores padrão no session_state
        if "vel_0" not in st.session_state:
            st.session_state.vel_0 = 25.0
        if "vel_1" not in st.session_state:
            st.session_state.vel_1 = 75.0

        st.markdown(
            """
            <style>
            .stButton > button {
                width: 100%;
                margin: 0;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        # Cria os botões dentro de um container com a classe personalizada
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Modo Competição", use_container_width=True): 
                st.session_state.start_pressed = True
        with col2:
            if st.button("Modo Teste", use_container_width=True):
                st.session_state.stop_pressed = True

        # Parte a baixo necessária para mostrar mensagens de sucesso ou erro no mesmo local

        if 'start_pressed' in st.session_state and st.session_state.start_pressed:
            st.success("Modo Competição Ativado!")
            st.session_state.start_pressed = False  # Reset the state
        if 'stop_pressed' in st.session_state and st.session_state.stop_pressed:
            st.error("Modo Teste Ativado!")
            st.session_state.stop_pressed = False  # Reset the state

        # Cria 2 colunas para organizar os componentes
        col1, col2 = st.columns(2)

        # Caixas de entrada para velocidade mínima e máxima
        with col1:
            vel_0 = st.number_input(
                "Velocidade Mínima", min_value=0.0, max_value=100.0, value=st.session_state.vel_0, step=1.0, key="vel_0_input"
            )
        with col2:
            vel_1 = st.number_input(
                "Velocidade Máxima", min_value=0.0, max_value=100.0, value=st.session_state.vel_1, step=1.0, key="vel_1_input"
            )

        # Verifica se vel_0 > vel_1
        if vel_0 > vel_1:
            st.error("Erro: Velocidade Mínima não pode ser maior que Velocidade Máxima!")
        else:
            # Atualiza os valores no session_state
            st.session_state.vel_0 = vel_0
            st.session_state.vel_1 = vel_1

            # Exibe os valores atualizados
            st.write(f"Velocidade Mínima: {st.session_state.vel_0}")
            st.write(f"Velocidade Máxima: {st.session_state.vel_1}")

# ----------------------------------------- Controles ------------------------------------------------        

    elif menu == "Controles":
        st.header("Controles")

        # Botões de Start/Stop
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Iniciar", use_container_width=True): 
                st.session_state.start_pressed = True
        with col2:
            if st.button("Parar", use_container_width=True):
                st.session_state.stop_pressed = True

        # Mensagens de feedback
        if 'start_pressed' in st.session_state and st.session_state.start_pressed:
            st.success("Sistema iniciado!")
            st.session_state.start_pressed = False
        if 'stop_pressed' in st.session_state and st.session_state.stop_pressed:
            st.error("Sistema parado!")
            st.session_state.stop_pressed = False

        # Adiciona espaço entre os controles
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Layout para as setas direcionais
        st.markdown("### Controle Direcional")
        
        # Container centralizado para as setas
        _, col_center, _ = st.columns([1, 1, 1])
        
        with col_center:
            # Subcolunas para as setas
            col1, col2, col3 = st.columns([1,1,1])
            with col1:
                if st.button("↖", key="upleft"):
                    st.session_state.upleft_pressed = True
            with col2:
                if st.button("↑", key="up"):
                    st.session_state.up_pressed = True
            with col3:
                if st.button("↗", key="upright"):
                    st.session_state.upright_pressed = True
                
            # Botões esquerda, baixo, direita na mesma linha
            left_col, mid_col, right_col = st.columns([1,1,1])
            with left_col:
                if st.button("←", key="left"):
                    st.session_state.left_pressed = True
            with mid_col:
                if st.button("⏹", key="stop"):
                    st.session_state.stop_pressed = True
            with right_col:
                if st.button("→", key="right"):
                    st.session_state.right_pressed = True

            # Botões esquerda, baixo, direita na mesma linha
            col7, col8, col9 = st.columns([1,1,1])
            with col7:
                if st.button("↙", key="downleft"):
                    st.session_state.downleft_pressed = True
            with col8:
                if st.button("↓", key="down"):
                    st.session_state.down_pressed = True
            with col9:
                if st.button("↘", key="downright"):
                    st.session_state.downright_pressed = True

        # Feedback das teclas pressionadas
        if 'upleft_pressed' in st.session_state and st.session_state.upleft_pressed:
            st.write("Movimento: Frente/Esquerda")
            st.session_state.upleft_pressed = False
        if 'up_pressed' in st.session_state and st.session_state.up_pressed:
            st.write("Movimento: Frente")
            st.session_state.up_pressed = False
        if 'upright_pressed' in st.session_state and st.session_state.upright_pressed:
            st.write("Movimento: Frente/Direita")
            st.session_state.upright_pressed = False
        if 'left_pressed' in st.session_state and st.session_state.left_pressed:
            st.write("Movimento: Esquerda")
            st.session_state.left_pressed = False
        if 'stop_pressed' in st.session_state and st.session_state.stop_pressed:
            st.write("Movimento: Parar")
            st.session_state.stop_pressed = False
        if 'right_pressed' in st.session_state and st.session_state.right_pressed:
            st.write("Movimento: Direita")
            st.session_state.right_pressed = False
        if 'downleft_pressed' in st.session_state and st.session_state.downleft_pressed:
            st.write("Movimento: Trás/Esquerda")
            st.session_state.downleft_pressed = False
        if 'down_pressed' in st.session_state and st.session_state.down_pressed:
            st.write("Movimento: Trás")
            st.session_state.down_pressed = False
        if 'downright_pressed' in st.session_state and st.session_state.downright_pressed:
            st.write("Movimento: Trás/Direita")
            st.session_state.downright_pressed = False



if __name__ == "__main__":
    main()