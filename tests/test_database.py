
import sqlite3

import pytest
import database


def test_tabelas_principais_existentes(tmp_path, monkeypatch):
    # Usa um banco temporário, sem tocar no banco real.
    banco_teste = tmp_path / "devstudy_test.db"
    monkeypatch.setattr(database, "CAMINHO_BANCO", banco_teste)

    database.criar_tabelas()

    conexao = database.conectar()

    try:
        tabelas = conexao.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
        """).fetchall()

        nomes = {tabela["name"] for tabela in tabelas}

        assert "anotacoes" in nomes
        assert "meta_diaria" in nomes
        assert "sessoes_estudo" in nomes
        assert "metas_semanais" in nomes
        assert "assuntos" in nomes

    finally:
        conexao.close()


def test_grade_ads_tem_23_disciplinas_sem_semestre_assumido(
    tmp_path, monkeypatch
):
    banco_teste = tmp_path / "devstudy_test.db"
    monkeypatch.setattr(database, "CAMINHO_BANCO", banco_teste)

    database.criar_tabelas()
    database.criar_tabelas()

    conexao = database.conectar()
    try:
        materias = conexao.execute(
            "SELECT nome, semestre FROM materias ORDER BY nome"
        ).fetchall()
        assert {item["nome"] for item in materias} == set(
            database.MATERIAS_INICIAIS
        )
        assert len(materias) == 23
        assert all(item["semestre"] is None for item in materias)
    finally:
        conexao.close()


def test_migracao_remove_materias_legadas_uma_vez_sem_apagar_cursos(
    tmp_path, monkeypatch
):
    banco_teste = tmp_path / "devstudy_test.db"
    monkeypatch.setattr(database, "CAMINHO_BANCO", banco_teste)

    database.criar_tabelas()
    conexao = database.conectar()
    try:
        conexao.execute(
            "DELETE FROM migracoes_aplicadas "
            "WHERE versao = 'grade_ads_limpeza_materias_teste_v1'"
        )
        cursor = conexao.execute(
            "INSERT INTO materias (nome) VALUES ('Python')"
        )
        materia_antiga_id = cursor.lastrowid
        cursor = conexao.execute("""
            INSERT INTO cursos (titulo, materia_id)
            VALUES ('Curso de teste', ?)
        """, (materia_antiga_id,))
        curso_id = cursor.lastrowid
        conexao.execute("""
            INSERT INTO anotacoes (titulo, materia, conteudo, categoria)
            VALUES ('Nota legada', 'Python', 'Preservar', 'Geral')
        """)
        conexao.execute("""
            INSERT INTO sessoes_estudo (materia, duracao_minutos)
            VALUES ('Python', 20)
        """)
        conexao.commit()
    finally:
        conexao.close()

    database.criar_tabelas()

    conexao = database.conectar()
    try:
        assert conexao.execute(
            "SELECT COUNT(*) FROM materias"
        ).fetchone()[0] == 23
        curso = conexao.execute(
            "SELECT id, materia_id FROM cursos WHERE id = ?",
            (curso_id,)
        ).fetchone()
        assert curso["id"] == curso_id
        assert curso["materia_id"] is None
        assert conexao.execute(
            "SELECT conteudo FROM anotacoes WHERE titulo = 'Nota legada'"
        ).fetchone()["conteudo"] == "Preservar"
        assert conexao.execute(
            "SELECT COUNT(*) FROM sessoes_estudo WHERE materia = 'Python'"
        ).fetchone()[0] == 1

        conexao.execute(
            "INSERT INTO materias (nome) VALUES ('Disciplina futura')"
        )
        conexao.commit()
    finally:
        conexao.close()

    database.criar_tabelas()
    conexao = database.conectar()
    try:
        assert conexao.execute(
            "SELECT id FROM materias WHERE nome = 'Disciplina futura'"
        ).fetchone() is not None
    finally:
        conexao.close()


def test_meta_diaria_inicial(tmp_path, monkeypatch):
    banco_teste = tmp_path / "devstudy_test.db"
    monkeypatch.setattr(database, "CAMINHO_BANCO", banco_teste)

    database.criar_tabelas()

    conexao = database.conectar()

    try:
        meta = conexao.execute("""
            SELECT minutos_meta
            FROM meta_diaria
            WHERE id = 1
        """).fetchone()

        assert meta is not None
        assert meta["minutos_meta"] == 60

    finally:
        conexao.close()


def test_conexao_aberta_fecha_conexao(tmp_path, monkeypatch):
    banco_teste = tmp_path / "devstudy_test.db"
    monkeypatch.setattr(database, "CAMINHO_BANCO", banco_teste)

    with database.conexao_aberta() as conexao:
        conexao.execute("""
            CREATE TABLE teste (
                id INTEGER PRIMARY KEY
            )
        """)

    # Uma conexão fechada não permite executar novas consultas.
    with pytest.raises(sqlite3.ProgrammingError):
        conexao.execute("SELECT 1")



def test_conexao_aberta_desfaz_transacao_em_erro(
    tmp_path, monkeypatch
):
    banco_teste = tmp_path / "devstudy_test.db"
    monkeypatch.setattr(database, "CAMINHO_BANCO", banco_teste)

    database.criar_tabelas()

    with pytest.raises(ValueError, match="erro de teste"):
        with database.conexao_aberta() as conexao:
            conexao.execute("""
                UPDATE meta_diaria
                SET minutos_meta = 90
                WHERE id = 1
            """)

            raise ValueError("erro de teste")

    # Confirma que a alteração foi desfeita.
    conexao_verificacao = database.conectar()

    try:
        resultado = conexao_verificacao.execute("""
            SELECT minutos_meta
            FROM meta_diaria
            WHERE id = 1
        """).fetchone()

        assert resultado["minutos_meta"] == 60

    finally:
        conexao_verificacao.close()

def test_migracao_adiciona_identificador_em_banco_antigo(
    tmp_path, monkeypatch
):
    banco_teste = tmp_path / "devstudy_test.db"
    monkeypatch.setattr(database, "CAMINHO_BANCO", banco_teste)

    # Simula uma versão antiga da tabela, sem identificador.
    conexao = sqlite3.connect(banco_teste)

    try:
        conexao.execute("""
            CREATE TABLE sessoes_estudo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                materia TEXT NOT NULL,
                duracao_minutos INTEGER NOT NULL,
                data_estudo TEXT NOT NULL DEFAULT '2026-01-01',
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conexao.execute("""
            INSERT INTO sessoes_estudo (
                materia, duracao_minutos
            )
            VALUES ('Python', 30)
        """)

        conexao.commit()

    finally:
        conexao.close()

    # A inicialização deve atualizar a tabela antiga.
    database.criar_tabelas()

    conexao = database.conectar()

    try:
        colunas = conexao.execute(
            "PRAGMA table_info(sessoes_estudo)"
        ).fetchall()

        nomes_colunas = {coluna["name"] for coluna in colunas}

        assert "identificador" in nomes_colunas

        # A migração não deve apagar os registros existentes.
        sessao = conexao.execute("""
            SELECT materia, duracao_minutos
            FROM sessoes_estudo
        """).fetchone()

        assert sessao["materia"] == "Python"
        assert sessao["duracao_minutos"] == 30

    finally:
        conexao.close()


def test_criar_tabelas_pode_ser_executado_mais_de_uma_vez(
    tmp_path, monkeypatch
):
    banco_teste = tmp_path / "devstudy_test.db"
    monkeypatch.setattr(database, "CAMINHO_BANCO", banco_teste)

    database.criar_tabelas()
    database.criar_tabelas()

    conexao = database.conectar()

    try:
        metas = conexao.execute("""
            SELECT COUNT(*) AS total
            FROM meta_diaria
            WHERE id = 1
        """).fetchone()

        assert metas["total"] == 1

    finally:
        conexao.close()


def test_migracao_de_assuntos_preserva_anotacoes_existentes(
    tmp_path, monkeypatch
):
    banco_teste = tmp_path / "devstudy_test.db"
    monkeypatch.setattr(database, "CAMINHO_BANCO", banco_teste)

    database.criar_tabelas()
    conexao = database.conectar()
    try:
        conexao.execute("""
            INSERT INTO anotacoes (titulo, materia, conteudo, categoria)
            VALUES ('Nota antiga', 'Python', 'Conteúdo preservado', 'Geral')
        """)
        conexao.commit()
    finally:
        conexao.close()

    database.criar_tabelas()

    conexao = database.conectar()
    try:
        anotacao = conexao.execute("""
            SELECT titulo, conteudo
            FROM anotacoes
            WHERE titulo = 'Nota antiga'
        """).fetchone()
        assert anotacao["conteudo"] == "Conteúdo preservado"
        assert conexao.execute(
            "SELECT COUNT(*) FROM assuntos"
        ).fetchone()[0] == 0
    finally:
        conexao.close()


def test_migracao_adiciona_assunto_em_anotacoes_antigas(
    tmp_path, monkeypatch
):
    banco_teste = tmp_path / "devstudy_test.db"
    monkeypatch.setattr(database, "CAMINHO_BANCO", banco_teste)

    conexao = sqlite3.connect(banco_teste)
    try:
        conexao.execute("""
            CREATE TABLE anotacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                materia TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conexao.execute("""
            INSERT INTO anotacoes (titulo, materia, conteudo)
            VALUES ('Registro legado', 'Python', 'Sem perda de conteúdo')
        """)
        conexao.commit()
    finally:
        conexao.close()

    database.criar_tabelas()

    conexao = database.conectar()
    try:
        nota = conexao.execute("""
            SELECT titulo, conteudo, assunto_id
            FROM anotacoes
            WHERE titulo = 'Registro legado'
        """).fetchone()
        assert nota["conteudo"] == "Sem perda de conteúdo"
        assert nota["assunto_id"] is None
    finally:
        conexao.close()
