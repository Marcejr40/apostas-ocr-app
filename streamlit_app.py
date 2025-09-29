```python
import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import io

st.set_page_config(page_title="Apostas OCR App", layout="wide")

st.title("📊 Acompanhamento de Apostas com OCR")

# Inicializa o DataFrame no estado da sessão
if "bets" not in st.session_state:
    st.session_state["bets"] = pd.DataFrame(columns=["Grupo", "Casa", "Descrição", "Valor", "Retorno", "Status"])

# Upload de imagem para OCR
st.header("📷 Importar aposta por print")
uploaded_file = st.file_uploader("Envie um print (JPEG/PNG)", type=["png", "jpg", "jpeg"])
if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="Print enviado", use_column_width=True)

    # OCR para extrair texto
    text = pytesseract.image_to_string(image, lang="por")
    st.text_area("Texto extraído:", text, height=150)

    # Opção de salvar como nova aposta
    if st.button("Salvar aposta extraída"):
        st.session_state["bets"] = pd.concat([
            st.session_state["bets"],
            pd.DataFrame([{
                "Grupo": "Manual",
                "Casa": "Desconhecida",
                "Descrição": text[:50] + "...",
                "Valor": 0,
                "Retorno": 0,
                "Status": "Pendente"
            }])
        ], ignore_index=True)
        st.success("Aposta salva!")

# Cadastro manual
st.header("✍️ Cadastrar aposta manualmente")
with st.form("manual_bet"):
    grupo = st.text_input("Grupo (ex: Grupo 1, Grupo VIP...)")
    casa = st.selectbox("Casa de aposta", ["Bet365", "Betano", "Outras"])
    descricao = st.text_input("Descrição da aposta")
    valor = st.number_input("Valor apostado (R$)", min_value=0.0, step=0.5)
    retorno = st.number_input("Retorno (R$)", min_value=0.0, step=0.5)
    status = st.selectbox("Resultado", ["Green", "Red", "Pendente"])
    submit = st.form_submit_button("Adicionar aposta")

    if submit:
        st.session_state["bets"] = pd.concat([
            st.session_state["bets"],
            pd.DataFrame([{
                "Grupo": grupo,
                "Casa": casa,
                "Descrição": descricao,
                "Valor": valor,
                "Retorno": retorno,
                "Status": status
            }])
        ], ignore_index=True)
        st.success("Aposta adicionada!")

# Exibição das apostas
st.header("📑 Histórico de apostas")
st.dataframe(st.session_state["bets"], use_container_width=True)

# Estatísticas
if not st.session_state["bets"].empty:
    total = len(st.session_state["bets"])
    greens = (st.session_state["bets"]["Status"] == "Green").sum()
    reds = (st.session_state["bets"]["Status"] == "Red").sum()
    pendentes = (st.session_state["bets"]["Status"] == "Pendente").sum()

    perc_green = (greens / total * 100) if total > 0 else 0

    st.subheader("📈 Estatísticas")
    st.metric("Total de apostas", total)
    st.metric("Greens", greens)
    st.metric("Reds", reds)
    st.metric("% de Acertos", f"{perc_green:.2f}%")
    st.progress(perc_green / 100)
```

