import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import io

st.set_page_config(page_title="OCR Apostas", page_icon="🎰", layout="wide")

st.title("📊 OCR de Apostas - Versão Teste")

st.write("Faça upload de um print da aposta (green, red ou void) para extrair informações.")

uploaded_file = st.file_uploader("Envie um print da aposta", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
image = Image.open(uploaded_file)
st.image(image, caption="Imagem enviada", use_column_width=True)

```
# Converte imagem para texto
text = pytesseract.image_to_string(image, lang="por")
st.subheader("📝 Texto extraído:")
st.text(text)

# Exemplo simples: detectar se é Green, Red ou Void
status = None
if "Retorno Obtido R$0,00" in text or "Perdida" in text:
    status = "❌ Red"
elif "Retorno Obtido" in text and "R$0,00" not in text:
    status = "✅ Green"
elif "Anulado" in text:
    status = "⚪ Void"

if status:
    st.success(f"Status detectado: {status}")
else:
    st.warning("Não consegui identificar o status automaticamente.")
```
