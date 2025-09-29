```python
import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import io

# -------------------------------
# Configuração inicial
# -------------------------------
st.set_page_config(page_title="Leitor de Apostas OCR", layout="wide")

# Inicializa o DataFrame se não existir ainda
if "bets" not in st.session_state:
    st.session_state["bets"] = pd.DataFrame(columns=["Grupo", "Casa", "Descrição", "Valor", "Retorno", "Status"])

# -------------------------------
# Função para processar OCR
# -------------------------------
def process_image(uploaded_file):
    try:
        # Lê a imagem
        img = Image.open(uploaded_file)

        # Aplica OCR (forçando idioma português)
        text = pytesseract.image_to_string(img, lang="por")

        return text
    except Exception as e:
        return f"Erro ao executar OCR: {e}"

# -------------------------------
# Interface principal
# -------------------------------
st.title("📊 OCR de Apostas")

uploaded_file = st.file_uploader("Envie o print da aposta", type=["png", "jpg", "jpeg"])

if uploaded_file:
    st.image(uploaded_file, caption="Print enviado", use_container_width=True)

    # Processa imagem
    extracted_text = process_image(uploaded_file)

    st.subheader("📝 Texto reconhecido")
    st.write(extracted_text)

    # Preencher dados manualmente
    st.subheader("➕ Adicionar aposta")
    with st.form("add_bet"):
        grupo = st.text_input("Grupo")
        casa = st.text_input("Casa")
        descricao = st.text_area("Descrição")
        valor = st.number_input("Valor", min_value=0.0, step=1.0)
        retorno = st.number_input("Retorno", min_value=0.0, step=1.0)
        status = st.selectbox("Status", ["Green", "Red", "Void"])

        submit = st.form_submit_button("Salvar aposta")

        if submit:
            nova_linha = {
                "Grupo": grupo,
                "Casa": casa,
                "Descrição": descricao,
                "Valor": valor,
                "Retorno": retorno,
                "Status": status,
            }
            st.session_state["bets"] = pd.concat(
                [st.session_state["bets"], pd.DataFrame([nova_linha])],
                ignore_index=True,
            )
            st.success("✅ Aposta adicionada com sucesso!")

# -------------------------------
# Dashboard
# -------------------------------
if not st.session_state["bets"].empty:
    st.subheader("📈 Dashboard de Apostas")
    st.dataframe(st.session_state["bets"], use_container_width=True)

    # Lucro/Prejuízo
    st.subheader("💰 Lucro / Prejuízo por Status")
    resumo_status = (
        st.session_state["bets"]
        .groupby("Status")
        .agg({"Valor": "sum", "Retorno": "sum"})
    )
    resumo_status["Lucro"] = resumo_status["Retorno"] - resumo_status["Valor"]
    st.bar_chart(resumo_status["Lucro"], use_container_width=True)

    # Lucro por grupo
    st.subheader("👥 Lucro por Grupo")
    resumo_grupo = (
        st.session_state["bets"]
        .groupby("Grupo")
        .agg({"Valor": "sum", "Retorno": "sum"})
    )
    resumo_grupo["Lucro"] = resumo_grupo["Retorno"] - resumo_grupo["Valor"]
    st.bar_chart(resumo_grupo["Lucro"], use_container_width=True)
```
