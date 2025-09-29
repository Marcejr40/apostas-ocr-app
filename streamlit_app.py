import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import matplotlib.pyplot as plt

# Configuração inicial
st.set_page_config(page_title="Apostas OCR", layout="wide")

# Inicializa sessão
if "bets" not in st.session_state:
    st.session_state["bets"] = pd.DataFrame(columns=["Grupo", "Casa", "Descrição", "Valor", "Retorno", "Status"])

st.title("📊 Acompanhamento de Apostas (Básico Corrigido)")

# ---- UPLOAD E OCR ----
uploaded_file = st.file_uploader("Envie o print da aposta", type=["png", "jpg", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Print enviado", use_container_width=True)

    try:
        text = pytesseract.image_to_string(image, lang="por")
        st.text_area("Texto detectado", text, height=150)

        # Detecta status com tolerância a erros do OCR
        text_lower = text.lower()

        if any(x in text_lower for x in ["green", "gren", "grenn", "ganho", "vencida"]):
            status = "Green"
        elif any(x in text_lower for x in ["red", "perdida", "loss"]):
            status = "Red"
        elif any(x in text_lower for x in ["void", "anulada", "cancelada"]):
            status = "Void"
        else:
            status = "Pendente"

        # Entrada simulada
        nova_aposta = {
            "Grupo": "Manual",
            "Casa": "Detectar",
            "Descrição": text[:50] + "...",
            "Valor": 100.0,
            "Retorno": 200.0 if status == "Green" else 0.0,
            "Status": status,
        }
        st.session_state["bets"] = pd.concat([st.session_state["bets"], pd.DataFrame([nova_aposta])], ignore_index=True)

    except Exception as e:
        st.error(f"Erro ao executar OCR: {e}")

# ---- TABELA ----
st.subheader("📑 Apostas Registradas")
st.dataframe(st.session_state["bets"], use_container_width=True)

# ---- RESUMO ----
df = st.session_state["bets"]


