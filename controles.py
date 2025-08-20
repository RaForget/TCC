import streamlit as st

def show_controles():
    st.header("Controles")

    # Botões de Start/Stop
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Iniciar", use_container_width=True): 
            st.session_state.start_pressed = True
    with col2:
        if st.button("Parar", use_container_width=True):
            st.session_state.stop_pressed = True

    if 'start_pressed' in st.session_state and st.session_state.start_pressed:
        st.success("Sistema iniciado!")
        st.session_state.start_pressed = False
    if 'stop_pressed' in st.session_state and st.session_state.stop_pressed:
        st.error("Sistema parado!")
        st.session_state.stop_pressed = False

    st.markdown("<br>", unsafe_allow_html=True)
    
    st.markdown("### Controle Direcional")
    
    _, col_center, _ = st.columns([1, 1, 1])
    
    with col_center:
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

    # Feedback das teclas
    for direction in ['upleft', 'up', 'upright', 'left', 'stop', 'right', 
                     'downleft', 'down', 'downright']:
        if f'{direction}_pressed' in st.session_state and getattr(st.session_state, f'{direction}_pressed'):
            movimento = direction.replace('up', 'Frente/').replace('down', 'Trás/') \
                              .replace('left', 'Esquerda').replace('right', 'Direita') \
                              .replace('stop', 'Parar')
            st.write(f"Movimento: {movimento}")
            setattr(st.session_state, f'{direction}_pressed', False)