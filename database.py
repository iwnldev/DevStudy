
import sqlite3
from pathlib import Path
from contextlib import contextmanager


# Descobre a pasta principal do projeto
PASTA_PROJETO = Path(__file__).resolve().parent

# Define onde o banco de dados será salvo
PASTA_DADOS = PASTA_PROJETO / "instance"

# Cria a pasta caso ela ainda não exista
PASTA_DADOS.mkdir(parents=True, exist_ok=True)

# Define o caminho completo do banco
CAMINHO_BANCO = PASTA_DADOS / "devstudy.db"


def conectar():
    """Cria uma conexão com o banco de dados."""
    conexao = sqlite3.connect(CAMINHO_BANCO)
    conexao.row_factory = sqlite3.Row
    return conexao


@contextmanager
def conexao_aberta():
    """Gerencia a transação e fecha a conexão ao terminar."""
    conexao = conectar()

    try:
        with conexao:
            yield conexao
    finally:
        conexao.close()


def criar_tabelas():
    """Cria as tabelas e atualiza a estrutura do banco."""

    with conexao_aberta() as conexao:

        # Tabela de anotações
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS anotacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                materia TEXT NOT NULL,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Verifica as colunas existentes nas anotações
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

        # Tabela da meta diária
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS meta_diaria (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                minutos_meta INTEGER NOT NULL DEFAULT 60
            )
        """)

        # Tabela das sessões de estudo
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS sessoes_estudo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                materia TEXT NOT NULL,
                duracao_minutos INTEGER NOT NULL,
                data_estudo TEXT NOT NULL
                    DEFAULT (date('now', 'localtime')),
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                identificador TEXT
            )
        """)

        # Verifica as colunas existentes nas sessões
        colunas_sessoes = conexao.execute(
            "PRAGMA table_info(sessoes_estudo)"
        ).fetchall()

        nomes_colunas_sessoes = [
            coluna["name"] for coluna in colunas_sessoes
        ]

        # Atualiza bancos antigos sem apagar os registros
        if "identificador" not in nomes_colunas_sessoes:
            conexao.execute("""
                ALTER TABLE sessoes_estudo
                ADD COLUMN identificador TEXT
            """)

        # Impede a repetição de identificadores não nulos
        conexao.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_sessoes_identificador
            ON sessoes_estudo (identificador)
        """)

        # Cria a meta inicial de 60 minutos, caso não exista
        conexao.execute("""
            INSERT OR IGNORE INTO meta_diaria (
                id,
                minutos_meta
            )
            VALUES (1, 60)
        """)


if __name__ == "__main__":
    criar_tabelas()
    print("Banco de dados criado e verificado com sucesso!")
