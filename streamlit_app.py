import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image

st.set_page_config(page_title="Leitor de Apostas OCR", layout="wide")
st.title("📊 OCR de Apostas - Teste")

# Inicializa o DataFrame
if "bets" not in st.session_state:
    st.session_state["bets"] = pd.DataFrame(columns=["Grupo", "Casa", "Descrição", "Valor", "Retorno", "Status"])

def process_image_file(uploaded_file):
    """Extrai texto e detecta status automático"""
    try:
        img = Image.open(uploaded_file)
    except Exception as e:
        return None, None, f"Erro ao abrir a imagem: {e}"

    # Tenta OCR em português, se falhar cai no padrão
    try:
        text = pytesseract.image_to_string(img, lang="por")
    except Exception:
        text = pytesseract.image_to_string(img)

    # Detecta status no texto
    status = "Pendente"
    lower_text = text.lower()
    if any(word in lower_text for word in ["green", "ganho", "ganhou"]):
        status = "Green"
    elif any(word in lower_text for word in ["red", "perdida", "perdeu"]):
        status = "Red"
    elif any(word in lower_text for word in ["void", "anulada", "cancelada"]):
        status = "Void"

    return text, status, None

# Upload de arquivo
uploaded_file = st.file_uploader("Envie um print (PNG/JPG)", type=["png", "jpg", "jpeg"])
if uploaded_file:
    st.image(uploaded_file, caption="Print enviado", use_container_width=True)

    extracted_text, auto_status, ocr_msg = process_image_file(uploaded_file)

    if extracted_text is None:
        st.error(ocr_msg)
    else:
        st.subheader("📝 Texto extraído")
        st.text_area("", extracted_text, height=180)

        st.subheader("➕ Adicionar aposta")
        with st.form("add_bet"):
            grupo = st.text_input("Grupo", value="Grupo 1")
            casa = st.text_input("Casa", value="")
            descricao = st.text_area("Descrição", value=(extracted_text or "")[:200])
            valor = st.number_input("Valor apostado (R$)", min_value=0.0, step=0.5, format="%.2f")
            retorno = st.number_input("Retorno (R$)", min_value=0.0, step=0.5, format="%.2f")
            status = st.selectbox("Status", ["Green", "Red", "Void", "Pendente"], 
                                  index=["Green","Red","Void","Pendente"].index(auto_status))

            submit = st.form_submit_button("Salvar aposta")
            if submit:
                nova_linha = {
                    "Grupo": grupo,
                    "Casa": casa,
                    "Descrição": descricao,
                    "Valor": float(valor),
                    "Retorno": float(retorno),
                    "Status": status
                }
                st.session_state["bets"] = pd.concat(
                    [st.session_state["bets"], pd.DataFrame([nova_linha])],
                    ignore_index=True
                )
                st.success(f"✅ Aposta adicionada (Status detectado: {status})")

# Dashboard
if not st.session_state["bets"].empty:
    st.subheader("📑 Histórico de apostas")
    st.dataframe(st.session_state["bets"], use_container_width=True)

    st.subheader("📈 Estatísticas")
    df = st.session_state["bets"]
    resumo = df.groupby("Status").size()
    st.bar_chart(resumo, use_container_width=True)

