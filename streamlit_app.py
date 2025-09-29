import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image

st.set_page_config(page_title="Leitor de Apostas OCR", layout="wide")
st.title("📊 OCR de Apostas - Teste")

# Inicializa o DataFrame no estado da sessão
if "bets" not in st.session_state:
    st.session_state["bets"] = pd.DataFrame(columns=["Grupo", "Casa", "Descrição", "Valor", "Retorno", "Status"])

def process_image_file(uploaded_file):
    """Tenta extrair texto da imagem: primeiro em 'por', se falhar tenta sem lingua."""
    try:
        img = Image.open(uploaded_file)
    except Exception as e:
        return None, f"Erro ao abrir a imagem: {e}"

    # Primeiro tenta em português
    try:
        text = pytesseract.image_to_string(img, lang="por")
        return text, None
    except Exception as e_por:
        # tenta sem especificar idioma (fallback)
        try:
            text = pytesseract.image_to_string(img)
            return text, f"Aviso: falha no 'por', usando fallback. Detalhe: {e_por}"
        except Exception as e_all:
            return None, f"Erro ao executar OCR: {e_por} | fallback falhou: {e_all}"

# Upload
uploaded_file = st.file_uploader("Envie um print (PNG/JPG)", type=["png", "jpg", "jpeg"])
if uploaded_file:
    st.image(uploaded_file, caption="Print enviado", use_container_width=True)

    extracted_text, ocr_msg = process_image_file(uploaded_file)

    if extracted_text is None:
        st.error(ocr_msg)
    else:
        if ocr_msg:
            st.warning(ocr_msg)
        st.subheader("📝 Texto extraído:")
        st.text_area("", extracted_text, height=180)

    # Formulário para salvar o registro (preencha/ajuste os campos)
    st.subheader("➕ Adicionar aposta (editar antes de salvar)")
    with st.form("add_bet"):
        grupo = st.text_input("Grupo", value="Grupo 1")
        casa = st.text_input("Casa", value="")
        descricao = st.text_area("Descrição", value=(extracted_text or "")[:200])
        valor = st.number_input("Valor apostado (R$)", min_value=0.0, step=0.5, format="%.2f")
        retorno = st.number_input("Retorno (R$)", min_value=0.0, step=0.5, format="%.2f")
        status = st.selectbox("Status", ["Green", "Red", "Void", "Pendente"], index=3)
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
            st.success("✅ Aposta adicionada!")

# Mostrar histórico e dashboard simples
if not st.session_state["bets"].empty:
    st.subheader("📑 Histórico de apostas")
    st.dataframe(st.session_state["bets"], use_container_width=True)

    st.subheader("📈 Estatísticas rápidas")
    df = st.session_state["bets"]
    total = len(df)
    greens = (df["Status"] == "Green").sum()
    reds = (df["Status"] == "Red").sum()
    voids = (df["Status"] == "Void").sum()
    perc_green = (greens / total * 100) if total > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", total)
    c2.metric("Greens", greens)
    c3.metric("Reds", reds)
    c4.metric("Voids", voids)
    st.metric("% Acertos (Green)", f"{perc_green:.2f}%")
    st.progress(min(max(perc_green / 100, 0.0), 1.0))
