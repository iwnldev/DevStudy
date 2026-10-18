
import sqlite3
from pathlib import Path

# Descobre a pasta principal do projeto
PASTA_PROJETO = Path(__file__).resolve().parent

# Define onde o banco de dados será salvo
PASTA_DADOS = PASTA_PROJETO / "instance"

# Cria a pasta caso ela ainda não exista
PASTA_DADOS.mkdir(exist_ok=True)

# Define o caminho completo do banco
CAMINHO_BANCO = PASTA_DADOS / "devstudy.db"


def conectar():
    conexao = sqlite3.connect(CAMINHO_BANCO)
    conexao.row_factory = sqlite3.Row
    return conexao


def criar_tabelas():
    with conectar() as conexao:
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS anotacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                materia TEXT NOT NULL,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Verifica quais colunas já existem
        colunas = conexao.execute(
            "PRAGMA table_info(anotacoes)"
        ).fetchall()

        nomes_colunas = [
            coluna["name"] for coluna in colunas
        ]

        # Adiciona categoria se ainda não existir
        if "categoria" not in nomes_colunas:
            conexao.execute("""
                ALTER TABLE anotacoes
                ADD COLUMN categoria TEXT NOT NULL DEFAULT 'Geral'
            """)

        # Adiciona favoritos se ainda não existir
        if "favorita" not in nomes_colunas:
            conexao.execute("""
                ALTER TABLE anotacoes
                ADD COLUMN favorita INTEGER NOT NULL DEFAULT 0
            """)

            
        # Cria a tabela que guarda a meta diária
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS meta_diaria (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                minutos_meta INTEGER NOT NULL DEFAULT 60
            )
        """)

        # Cria a tabela que registra as sessões de estudo
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS sessoes_estudo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                materia TEXT NOT NULL,
                duracao_minutos INTEGER NOT NULL,
                data_estudo TEXT NOT NULL DEFAULT (date('now', 'localtime')),
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Define a meta inicial de 60 minutos, caso ainda não exista
        conexao.execute("""
            INSERT OR IGNORE INTO meta_diaria (id, minutos_meta)
            VALUES (1, 60)
        """)

if __name__ == "__main__":
    criar_tabelas()
    print("Banco de dados criado e verificado com sucesso!")
