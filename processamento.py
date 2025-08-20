import streamlit as st
from terminal_handler import get_terminal_output, process_terminal_data

def update_velocity_data():
    """
    Obtém e processa os dados de velocidade linear e angular do terminal
    Retorna um dicionário com as velocidades processadas
    """
    terminal_data = get_terminal_output()
    if terminal_data:
        velocidade = process_terminal_data(terminal_data)
        if velocidade:
            return {
                "Linear": velocidade["Linear"],
                "Angular": velocidade["Angular"]
            }
    return None

def process_position_data():
    """
    Processa os dados de posição do robô
    """
    # Por enquanto retornando valores fixos como exemplo
    return {
        "Linear": 0.0,
        "Angular": 0.0
    }