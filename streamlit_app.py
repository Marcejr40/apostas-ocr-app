import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import io

st.set_page_config(page_title="Apostas OCR App", layout="wide")

st.title("📊 Acompanhamento de Apostas com OCR")

# Inicializa o DataFrame no estado da sessão
if "bets" not in st.session_state:
    st.session_state["bets"] = pd.DataFrame(
        columns=["Grupo", "Casa", "Descrição", "Valor", "Retorno", "Status"]
    )

# Upload de imagem para OCR
st.header("📷 Importar aposta por print")
uploaded_file = st.file_uploader("Envie um print (JPEG/PNG)", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="Print enviado", use_column_width=True)

    # OCR para extrair texto
    try:
        text = pytesseract.image_to_string(image, lang="por")
    except Exception as e:
        text = ""
        st.error("Erro ao executar OCR: " + str(e))

    st.subheader("📝 Texto extraído:")
    st.text_area("", text, height=150)

    # Botão para salvar como aposta extraída (preenche com valores padrão, você pode editar depois)
    if st.button("Salvar aposta extraída"):
        nova = {
            "Grupo": "Manual",
            "Casa": "Desconhecida",
            "Descrição": (text or "")[:80] + "...",
            "Valor": 0.0,
            "Retorno": 0.0,
            "Status": "Pendente"
        }
        st.session_state["bets"] = pd.concat(
            [st.session_state["bets"], pd.DataFrame([nova])],
            ignore_index=True
        )
        st.success("Aposta salva na lista (edite os valores conforme necessário).")

# Cadastro manual
st.header("✍️ Cadastrar aposta manualmente")
with st.form("manual_bet"):
    grupo = st.text_input("Grupo (ex: Grupo 1, Grupo VIP...)")
    casa = st.selectbox("Casa de aposta", ["Bet365", "Betano", "Outras"])
    descricao = st.text_input("Descrição da aposta")
    valor = st.number_input("Valor apostado (R$)", min_value=0.0, step=0.5, format="%.2f")
    retorno = st.number_input("Retorno (R$)", min_value=0.0, step=0.5, format="%.2f")
    status = st.selectbox("Resultado", ["Green", "Red", "Pendente", "Void"])
    submit = st.form_submit_button("Adicionar aposta")

    if submit:
        st.session_state["bets"] = pd.concat(
            [
                st.session_state["bets"],
                pd.DataFrame([{
                    "Grupo": grupo,
                    "Casa": casa,
                    "Descrição": descricao,
                    "Valor": float(valor),
                    "Retorno": float(retorno),
                    "Status": status
                }])
            ],
            ignore_index=True
        )
        st.success("Aposta adicionada!")

# Exibição das apostas
st.header("📑 Histórico de apostas")
st.dataframe(st.session_state["bets"], use_container_width=True)

# Estatísticas e % de acerto
if not st.session_state["bets"].empty:
    total = len(st.session_state["bets"])
    greens = (st.session_state["bets"]["Status"] == "Green").sum()
    reds = (st.session_state["bets"]["Status"] == "Red").sum()
    voids = (st.session_state["bets"]["Status"] == "Void").sum()
    pendentes = (st.session_state["bets"]["Status"] == "Pendente").sum()

    perc_green = (greens / total * 100) if total > 0 else 0.0

    st.subheader("📈 Estatísticas")
    cols = st.columns(4)
    cols[0].metric("Total de apostas", total)
    cols[1].metric("Greens", greens)
    cols[2].metric("Reds", reds)
    cols[3].metric("Voids", voids)

    st.metric("% de Acertos (Green)", f"{perc_green:.2f}%")
    st.progress(min(max(perc_green / 100, 0.0), 1.0))


