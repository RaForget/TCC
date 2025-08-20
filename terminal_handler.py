import subprocess
import streamlit as st
import re
import os

def get_terminal_output():
    """
    Executa get.py e retorna sua saída do terminal de forma segura
    """
    try:
        # Tenta executar o get.py
        script_dir = os.path.dirname(os.path.abspath(__file__))
        get_script = os.path.join(script_dir, 'get.py')
        
        result = subprocess.run(['python', get_script], 
                              capture_output=True, 
                              text=True,
                              timeout=2)  # Timeout de 2 segundos
        
        if result.returncode == 0 and result.stdout:
            return result.stdout.strip()
        return None
            
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None

def process_terminal_data(terminal_data):
    """
    Processa os dados de velocidade linear e angular do terminal
    """
    try:
        # Usando regex para extrair os valores de velocidade
        pattern = r"Linear Velocity: ([-\d.]+), Angular Velocity: ([-\d.]+)"
        match = re.search(pattern, terminal_data)
        
        if match:
            velocidade = {
                "Linear": float(match.group(1)),
                "Angular": float(match.group(2))
            }
            return velocidade
        else:
            st.warning("Formato de dados não reconhecido")
            return None
            
    except Exception as e:
        st.error(f"Erro ao processar dados: {e}")
        return None