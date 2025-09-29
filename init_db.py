import sqlite3

# Cria banco e tabela
conn = sqlite3.connect("apostas.db")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS apostas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    criado_em TEXT,
    grupo TEXT,
    casa TEXT,
    descricao TEXT,
    valor REAL,
    retorno REAL,
    lucro REAL,
    status TEXT,
    odd REAL
)
""")

conn.commit()
conn.close()

print("Banco inicializado com sucesso!")
