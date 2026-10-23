
import sqlite3
from pathlib import Path
from contextlib import contextmanager


# ==========================================
# CONFIGURAÇÃO DO BANCO DE DADOS
# ==========================================

PASTA_PROJETO = Path(__file__).resolve().parent

PASTA_DADOS = PASTA_PROJETO / "instance"
PASTA_DADOS.mkdir(parents=True, exist_ok=True)

CAMINHO_BANCO = PASTA_DADOS / "devstudy.db"


# ==========================================
# MATÉRIAS INICIAIS
# ==========================================

MATERIAS_INICIAIS = [
    "Python",
    "JavaScript",
    "Banco de dados",
    "Redes de computadores",
    "Faculdade - ADS",
    "Geral",
]


# ==========================================
# CONEXÃO COM O BANCO
# ==========================================

def conectar():
    """Abre uma conexão com o banco SQLite."""
    conexao = sqlite3.connect(CAMINHO_BANCO)

    # Permite acessar as colunas pelo nome.
    conexao.row_factory = sqlite3.Row

    # Habilita as chaves estrangeiras nesta conexão.
    conexao.execute("PRAGMA foreign_keys = ON")

    return conexao


# ==========================================
# CONTEXTO PARA GERENCIAR TRANSAÇÕES
# ==========================================

@contextmanager
def conexao_aberta():
    """
    Abre uma conexão e gerencia automaticamente
    commit, rollback e fechamento.
    """
    conexao = conectar()

    try:
        yield conexao
        conexao.commit()

    except Exception:
        conexao.rollback()
        raise

    finally:
        conexao.close()


# ==========================================
# CRIAÇÃO E ATUALIZAÇÃO DAS TABELAS
# ==========================================

def criar_tabelas():
    """Cria as tabelas necessárias sem apagar os dados existentes."""

    with conexao_aberta() as conexao:

        # --------------------------------------
        # ANOTAÇÕES
        # --------------------------------------

        conexao.execute("""
            CREATE TABLE IF NOT EXISTS anotacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                materia TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Verifica as colunas existentes.
        colunas_anotacoes = {
            coluna["name"]
            for coluna in conexao.execute(
                "PRAGMA table_info(anotacoes)"
            ).fetchall()
        }

        # Adiciona categoria caso seja um banco antigo.
        if "categoria" not in colunas_anotacoes:
            conexao.execute("""
                ALTER TABLE anotacoes
                ADD COLUMN categoria TEXT NOT NULL DEFAULT 'Geral'
            """)

        # Adiciona favorita caso seja um banco antigo.
        if "favorita" not in colunas_anotacoes:
            conexao.execute("""
                ALTER TABLE anotacoes
                ADD COLUMN favorita INTEGER NOT NULL DEFAULT 0
            """)

        # --------------------------------------
        # META DIÁRIA
        # --------------------------------------

        conexao.execute("""
            CREATE TABLE IF NOT EXISTS meta_diaria (
                id INTEGER PRIMARY KEY,
                minutos_meta INTEGER NOT NULL DEFAULT 60
            )
        """)

        # --------------------------------------
        # SESSÕES DE ESTUDO
        # --------------------------------------

        conexao.execute("""
            CREATE TABLE IF NOT EXISTS sessoes_estudo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                materia TEXT NOT NULL,
                duracao_minutos INTEGER NOT NULL,
                data_estudo TEXT NOT NULL DEFAULT (
                    date('now', 'localtime')
                ),
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migração para bancos criados antes do
        # identificador único de sessão.
        colunas_sessoes = {
            coluna["name"]
            for coluna in conexao.execute(
                "PRAGMA table_info(sessoes_estudo)"
            ).fetchall()
        }

        if "identificador" not in colunas_sessoes:
            conexao.execute("""
                ALTER TABLE sessoes_estudo
                ADD COLUMN identificador TEXT
            """)

        # Impede que a mesma requisição de sessão
        # seja registrada mais de uma vez.
        conexao.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_sessoes_identificador
            ON sessoes_estudo (identificador)
        """)

        # --------------------------------------
        # MATÉRIAS
        # --------------------------------------

        conexao.execute("""
            CREATE TABLE IF NOT EXISTS materias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                descricao TEXT NOT NULL DEFAULT '',
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insere as matérias iniciais sem duplicá-las.
        for materia in MATERIAS_INICIAIS:
            conexao.execute("""
                INSERT OR IGNORE INTO materias (nome)
                VALUES (?)
            """, (materia,))

        # --------------------------------------
        # CURSOS
        # --------------------------------------

        conexao.execute("""
            CREATE TABLE IF NOT EXISTS cursos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                descricao TEXT NOT NULL DEFAULT '',
                materia_id INTEGER,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (materia_id)
                    REFERENCES materias (id)
                    ON DELETE SET NULL
            )
        """)

        # --------------------------------------
        # MÓDULOS DOS CURSOS
        # --------------------------------------

        conexao.execute("""
            CREATE TABLE IF NOT EXISTS modulos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                curso_id INTEGER NOT NULL,
                titulo TEXT NOT NULL,
                descricao TEXT NOT NULL DEFAULT '',
                ordem INTEGER NOT NULL DEFAULT 1,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (curso_id)
                    REFERENCES cursos (id)
                    ON DELETE CASCADE
            )
        """)

        
        # --------------------------------------
        # AULAS DOS MÓDULOS
        # --------------------------------------

        conexao.execute("""
            CREATE TABLE IF NOT EXISTS aulas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                modulo_id INTEGER NOT NULL,
                titulo TEXT NOT NULL,
                conteudo TEXT NOT NULL DEFAULT '',
                ordem INTEGER NOT NULL DEFAULT 1,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (modulo_id)
                    REFERENCES modulos (id)
                    ON DELETE CASCADE
            )
        """)


        # --------------------------------------
        # META DIÁRIA PADRÃO
        # --------------------------------------

        conexao.execute("""
            INSERT OR IGNORE INTO meta_diaria (
                id,
                minutos_meta
            )
            VALUES (1, 60)
        """)


# ==========================================
# EXECUÇÃO DIRETA DO ARQUIVO
# ==========================================

if __name__ == "__main__":
    criar_tabelas()
    print("Banco de dados criado e verificado com sucesso!")
