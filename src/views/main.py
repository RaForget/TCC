# Para rodar o app, use o comando: python -m streamlit run .\src\views\main.py
import streamlit as st
import sys
import base64
from pathlib import Path

# Adiciona o diretório raiz ao PYTHONPATH
root_dir = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, root_dir)

# Imports absolutos
from src.handlers.processamento import update_velocity_data, process_position_data
from src.views.parametrizacao import show_parametrizacao
from src.views.controles import show_controles

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
                image_path = Path(__file__).parent.parent.parent / "assets" / "Simulacao.png"
                with open(image_path, "rb") as img:
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
                    margin-bottom: 20px;
                }
                .status-indicator {
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                    display: inline-block;
                    margin-right: 5px;
                }
                .status-online {
                    background-color: #28a745;
                }
                .status-offline {
                    background-color: #dc3545;
                }
                </style>
                """, 
                unsafe_allow_html=True
            )
    
            # Tenta atualizar dados de velocidade
            velocidade = update_velocity_data()
            
            # Indicador de status
            if velocidade is None:
                st.markdown(
                    """
                    <div style='text-align: center'>
                        <span class='status-indicator status-offline'></span>
                        <span>Offline</span>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
                # Mostra valores padrão quando offline
                st.markdown("<p class='centered-text'><strong>Velocidade</strong></p>", 
                          unsafe_allow_html=True)
                st.markdown(
                    "<p class='centered-text'>Linear: 0.0<br>Angular: 0.0</p>",
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    """
                    <div style='text-align: center'>
                        <span class='status-indicator status-online'></span>
                        <span>Online</span>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
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
        show_parametrizacao()

# ----------------------------------------- Controles ------------------------------------------------        

    elif menu == "Controles":
        show_controles()

if __name__ == "__main__":
    main()