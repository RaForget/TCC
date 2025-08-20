import streamlit as st

def show_parametrizacao():
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

    # Cria os botões dentro de um container
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Modo Competição", use_container_width=True): 
            st.session_state.start_pressed = True
    with col2:
        if st.button("Modo Teste", use_container_width=True):
            st.session_state.stop_pressed = True

    if 'start_pressed' in st.session_state and st.session_state.start_pressed:
        st.success("Modo Competição Ativado!")
        st.session_state.start_pressed = False
    if 'stop_pressed' in st.session_state and st.session_state.stop_pressed:
        st.error("Modo Teste Ativado!")
        st.session_state.stop_pressed = False

    # Cria 2 colunas para velocidades
    col1, col2 = st.columns(2)

    with col1:
        vel_0 = st.number_input(
            "Velocidade Mínima", min_value=0.0, max_value=100.0, 
            value=st.session_state.vel_0, step=1.0, key="vel_0_input"
        )
    with col2:
        vel_1 = st.number_input(
            "Velocidade Máxima", min_value=0.0, max_value=100.0, 
            value=st.session_state.vel_1, step=1.0, key="vel_1_input"
        )

    if vel_0 > vel_1:
        st.error("Erro: Velocidade Mínima não pode ser maior que Velocidade Máxima!")
    else:
        st.session_state.vel_0 = vel_0
        st.session_state.vel_1 = vel_1
        st.write(f"Velocidade Mínima: {st.session_state.vel_0}")
        st.write(f"Velocidade Máxima: {st.session_state.vel_1}")