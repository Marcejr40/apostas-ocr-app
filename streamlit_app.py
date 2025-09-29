```python
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

st.title("📊 Acompanhamento de Apostas com OCR")

# ---- UPLOAD E OCR ----
st.header("📸 Ler Print da Aposta")
uploaded_file = st.file_uploader("Envie o print da aposta", type=["png", "jpg", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Print enviado", use_container_width=True)

    try:
        text = pytesseract.image_to_string(image, lang="por")
        st.text_area("Texto detectado", text, height=150)

        # Exemplo de parsing simples (ajustar conforme padrão das casas de aposta)
        if "green" in text.lower():
            status = "Green"
        elif "red" in text.lower():
            status = "Red"
        elif "void" in text.lower():
            status = "Void"
        else:
            status = "Pendente"

        # Entrada padrão simulada
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

# ---- TABELA DE APOSTAS ----
st.header("📑 Apostas Registradas")
st.dataframe(st.session_state["bets"], use_container_width=True)

# ---- RESUMO ----
st.header("📊 Resumo de Resultados")

df = st.session_state["bets"]

if not df.empty:
    df["Lucro"] = df["Retorno"] - df["Valor"]

    total_reais = df["Lucro"].sum()
    total_unidades = df["Lucro"].sum() / df["Valor"].mean() if df["Valor"].mean() > 0 else 0

    col1, col2 = st.columns(2)
    col1.metric("💰 Lucro/Prejuízo (R$)", f"{total_reais:.2f}")
    col2.metric("📏 Lucro/Prejuízo (Unidades)", f"{total_unidades:.2f}")

# ---- GRÁFICOS ----
st.header("📈 Gráficos de Performance")

if not df.empty:
    # Gráfico por grupo
    fig1, ax1 = plt.subplots()
    df.groupby("Grupo")["Lucro"].sum().plot(kind="bar", ax=ax1)
    ax1.set_title("Lucro por Grupo")
    st.pyplot(fig1)

    # Gráfico evolução
    fig2, ax2 = plt.subplots()
    df["Lucro"].cumsum().plot(ax=ax2)
    ax2.set_title("Evolução do Lucro ao Longo do Tempo")
    st.pyplot(fig2)
```
