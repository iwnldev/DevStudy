
from database import conectar

with conectar() as conexao:
    tabelas = conexao.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' ORDER BY name"
    ).fetchall()

    print("Tabelas encontradas:")
    for tabela in tabelas:
        print("-", tabela["name"])

    meta = conexao.execute(
        "SELECT * FROM meta_diaria"
    ).fetchone()

    print("\nMeta diária cadastrada:")
    print(dict(meta) if meta else "Nenhuma meta encontrada.")
