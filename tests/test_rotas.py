
import pytest
from app import app
import database


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    # Cria um banco exclusivo para os testes
    banco_teste = tmp_path / "devstudy_test.db"

    # Faz o módulo database usar o banco temporário
    monkeypatch.setattr(
        database,
        "CAMINHO_BANCO",
        banco_teste
    )

    # Prepara as tabelas do banco de teste
    database.criar_tabelas()

    # Configura o Flask para testes
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "chave-exclusiva-para-testes"
    app.config["WTF_CSRF_ENABLED"] = False

    with app.test_client() as cliente:
        yield cliente


def test_pagina_inicial_responde(cliente):
    resposta = cliente.get("/")

    assert resposta.status_code == 200


def test_cadastrar_anotacao(cliente):
    resposta = cliente.post(
        "/nova-anotacao",
        data={
            "titulo": "Introdução ao Python",
            "materia": "Python",
            "conteudo": "Aprendendo variáveis e tipos de dados.",
            "categoria": "Programação"
        },
        follow_redirects=True
    )

    assert resposta.status_code == 200

    # Confere se a anotação foi realmente salva
    conexao = database.conectar()

    try:
        anotacao = conexao.execute("""
            SELECT titulo, materia, conteudo, categoria
            FROM anotacoes
            WHERE titulo = ?
        """, ("Introdução ao Python",)).fetchone()

        assert anotacao is not None
        assert anotacao["materia"] == "Python"
        assert anotacao["conteudo"] == (
            "Aprendendo variáveis e tipos de dados."
        )
        assert anotacao["categoria"] == "Programação"

    finally:
        conexao.close()


def test_cadastro_rejeita_titulo_vazio(cliente):
    resposta = cliente.post(
        "/nova-anotacao",
        data={
            "titulo": "   ",
            "materia": "Python",
            "conteudo": "Conteúdo de teste",
            "categoria": "Programação"
        },
        follow_redirects=True
    )

    assert resposta.status_code == 200

    conexao = database.conectar()

    try:
        anotacao = conexao.execute("""
            SELECT id
            FROM anotacoes
            WHERE conteudo = ?
        """, ("Conteúdo de teste",)).fetchone()

        assert anotacao is None

    finally:
        conexao.close()


def test_editar_anotacao(cliente):
    # Cria uma anotação inicial no banco de teste
    conexao = database.conectar()

    with conexao:
        cursor = conexao.execute("""
            INSERT INTO anotacoes
                (titulo, materia, conteudo, categoria)
            VALUES (?, ?, ?, ?)
        """, (
            "Título antigo",
            "Python",
            "Conteúdo antigo",
            "Programação"
        ))

        anotacao_id = cursor.lastrowid

    conexao.close()

    # Envia os novos dados para a rota de edição
    resposta = cliente.post(
        f"/editar-anotacao/{anotacao_id}",
        data={
            "titulo": "Título atualizado",
            "materia": "Python",
            "conteudo": "Conteúdo atualizado",
            "categoria": "Programação"
        },
        follow_redirects=True
    )

    assert resposta.status_code == 200

    conexao = database.conectar()

    try:
        anotacao = conexao.execute("""
            SELECT titulo, conteudo
            FROM anotacoes
            WHERE id = ?
        """, (anotacao_id,)).fetchone()

        assert anotacao["titulo"] == "Título atualizado"
        assert anotacao["conteudo"] == "Conteúdo atualizado"

    finally:
        conexao.close()


def test_excluir_anotacao(cliente):
    # Cria uma anotação no banco de teste
    conexao = database.conectar()

    with conexao:
        cursor = conexao.execute("""
            INSERT INTO anotacoes
                (titulo, materia, conteudo, categoria)
            VALUES (?, ?, ?, ?)
        """, (
            "Anotação para excluir",
            "Python",
            "Conteúdo temporário",
            "Programação"
        ))

        anotacao_id = cursor.lastrowid

    conexao.close()

    # Solicita a exclusão
    resposta = cliente.post(
        f"/excluir-anotacao/{anotacao_id}",
        follow_redirects=True
    )

    assert resposta.status_code == 200

    conexao = database.conectar()

    try:
        anotacao = conexao.execute("""
            SELECT id
            FROM anotacoes
            WHERE id = ?
        """, (anotacao_id,)).fetchone()

        assert anotacao is None

    finally:
        conexao.close()


def test_favoritar_anotacao(cliente):
    # Cria uma anotação inicialmente não favorita
    conexao = database.conectar()

    with conexao:
        cursor = conexao.execute("""
            INSERT INTO anotacoes
                (titulo, materia, conteudo, categoria, favorita)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "Anotação favorita",
            "Python",
            "Estudando testes",
            "Programação",
            0
        ))

        anotacao_id = cursor.lastrowid

    conexao.close()

    # Marca a anotação como favorita
    resposta = cliente.post(
        f"/favoritar-anotacao/{anotacao_id}",
        follow_redirects=True
    )

    assert resposta.status_code == 200

    conexao = database.conectar()

    try:
        anotacao = conexao.execute("""
            SELECT favorita
            FROM anotacoes
            WHERE id = ?
        """, (anotacao_id,)).fetchone()

        assert anotacao["favorita"] == 1

    finally:
        conexao.close()

    # Clica novamente para retirar dos favoritos
    resposta = cliente.post(
        f"/favoritar-anotacao/{anotacao_id}",
        follow_redirects=True
    )

    assert resposta.status_code == 200

    conexao = database.conectar()

    try:
        anotacao = conexao.execute("""
            SELECT favorita
            FROM anotacoes
            WHERE id = ?
        """, (anotacao_id,)).fetchone()

        assert anotacao["favorita"] == 0

    finally:
        conexao.close()


def test_definir_meta_diaria(cliente):
    resposta = cliente.post(
        "/definir-meta",
        data={"minutos_meta": "120"},
        follow_redirects=True
    )

    assert resposta.status_code == 200

    conexao = database.conectar()

    try:
        meta = conexao.execute("""
            SELECT minutos_meta
            FROM meta_diaria
            WHERE id = 1
        """).fetchone()

        assert meta is not None
        assert meta["minutos_meta"] == 120

    finally:
        conexao.close()


def test_registrar_sessao_estudo(cliente):
    identificador = "550e8400-e29b-41d4-a716-446655440000"

    resposta = cliente.post(
        "/registrar-estudo",
        data={
            "materia": "Python",
            "duracao_minutos": "25",
            "identificador": identificador
        },
        follow_redirects=True
    )

    assert resposta.status_code == 200

    conexao = database.conectar()

    try:
        sessao = conexao.execute("""
            SELECT materia, duracao_minutos, identificador
            FROM sessoes_estudo
            WHERE identificador = ?
        """, (identificador,)).fetchone()

        assert sessao is not None
        assert sessao["materia"] == "Python"
        assert sessao["duracao_minutos"] == 25
        assert sessao["identificador"] == identificador

    finally:
        conexao.close()


def test_impedir_sessao_duplicada(cliente):
    identificador = "550e8400-e29b-41d4-a716-446655440001"

    dados = {
        "materia": "Python",
        "duracao_minutos": "25",
        "identificador": identificador
    }

    # Tenta registrar a mesma sessão duas vezes
    primeira_resposta = cliente.post(
        "/registrar-estudo",
        data=dados,
        follow_redirects=True
    )

    segunda_resposta = cliente.post(
        "/registrar-estudo",
        data=dados,
        follow_redirects=True
    )

    assert primeira_resposta.status_code == 200
    assert segunda_resposta.status_code == 200

    conexao = database.conectar()

    try:
        resultado = conexao.execute("""
            SELECT COUNT(*) AS total
            FROM sessoes_estudo
            WHERE identificador = ?
        """, (identificador,)).fetchone()

        assert resultado["total"] == 1

    finally:
        conexao.close()


@pytest.mark.parametrize(
    "duracao",
    ["0", "1441", "abc"]
)
def test_registrar_estudo_rejeita_duracao_invalida(
    cliente,
    duracao
):
    identificador = "teste-duracao-invalida-" + duracao

    resposta = cliente.post(
        "/registrar-estudo",
        data={
            "materia": "Python",
            "duracao_minutos": duracao,
            "identificador": identificador
        },
        follow_redirects=True
    )

    assert resposta.status_code == 200

    conexao = database.conectar()

    try:
        sessao = conexao.execute("""
            SELECT id
            FROM sessoes_estudo
            WHERE identificador = ?
        """, (identificador,)).fetchone()

        assert sessao is None

    finally:
        conexao.close()


def test_registrar_estudo_rejeita_materia_invalida(cliente):
    identificador = "teste-materia-invalida-001"

    resposta = cliente.post(
        "/registrar-estudo",
        data={
            "materia": "Matéria inventada",
            "duracao_minutos": "25",
            "identificador": identificador
        },
        follow_redirects=True
    )

    assert resposta.status_code == 200

    conexao = database.conectar()

    try:
        sessao = conexao.execute("""
            SELECT id
            FROM sessoes_estudo
            WHERE identificador = ?
        """, (identificador,)).fetchone()

        assert sessao is None

    finally:
        conexao.close()
