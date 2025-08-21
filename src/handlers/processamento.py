import streamlit as st
from src.handlers.terminal_handler import get_terminal_output, process_terminal_data

def update_velocity_data():
    """
    Atualiza os dados de velocidade
    """
    terminal_data = get_terminal_output()
    if terminal_data:
        return process_terminal_data(terminal_data)
    return None

def process_position_data():
    """
    Processa dados de posição (placeholder)
    """
    return {
        "Linear": 0.0,
        "Angular": 0.0
    }