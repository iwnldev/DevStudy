
import uuid

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
    conexao = database.conectar()
    try:
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
    finally:
        conexao.close()

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
    conexao = database.conectar()
    try:
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
    finally:
        conexao.close()

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
    conexao = database.conectar()
    try:
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
    finally:
        conexao.close()

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


@pytest.mark.parametrize("duracao", ["0", "1441", "abc"])
def test_registrar_estudo_rejeita_duracao_invalida(
    cliente,
    duracao
):
    # Usa um UUID válido para que o teste isole a validação da duração.
    identificador = str(uuid.uuid4())

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
    identificador = str(uuid.uuid4())

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


def test_historico_sem_sessoes(cliente):
    resposta = cliente.get("/historico")

    assert resposta.status_code == 200
    assert b"Python" not in resposta.data


def test_historico_com_sessoes_de_estudo(cliente):
    identificador = str(uuid.uuid4())

    resposta = cliente.post(
        "/registrar-estudo",
        data={
            "materia": "Python",
            "duracao_minutos": "30",
            "identificador": identificador
        },
        follow_redirects=True
    )

    assert resposta.status_code == 200

    conexao = database.conectar()
    try:
        sessao = conexao.execute("""
            SELECT materia, duracao_minutos
            FROM sessoes_estudo
            WHERE identificador = ?
        """, (identificador,)).fetchone()
    finally:
        conexao.close()

    assert sessao is not None
    assert sessao["materia"] == "Python"
    assert sessao["duracao_minutos"] == 30

    resposta = cliente.get("/historico")

    assert resposta.status_code == 200
    assert b"Python" in resposta.data
    assert b"30" in resposta.data



def test_pesquisa_limita_texto_a_200_caracteres(
    cliente, monkeypatch
):
    import app as modulo_app

    pesquisa = "a" * 250
    valores_renderizacao = {}

    def render_template_falso(nome_template, **contexto):
        valores_renderizacao.update(contexto)
        return "Página de teste"

    monkeypatch.setattr(
        modulo_app,
        "render_template",
        render_template_falso
    )

    resposta = cliente.get(
        "/",
        query_string={"pesquisa": pesquisa}
    )

    assert resposta.status_code == 200
    assert valores_renderizacao["pesquisa"] == "a" * 200

def test_excluir_anotacao_inexistente(cliente):
    resposta = cliente.post(
        "/excluir-anotacao/99999",
        follow_redirects=True
    )

    assert resposta.status_code == 200


def test_favoritar_anotacao_inexistente(cliente):
    resposta = cliente.post(
        "/favoritar-anotacao/99999",
        follow_redirects=True
    )

    assert resposta.status_code == 200


def test_abrir_pagina_edicao_anotacao(cliente):
    conexao = database.conectar()
    try:
        with conexao:
            cursor = conexao.execute("""
                INSERT INTO anotacoes
                    (titulo, materia, conteudo, categoria)
                VALUES (?, ?, ?, ?)
            """, (
                "Anotação original",
                "Python",
                "Conteúdo original",
                "Programação"
            ))
            anotacao_id = cursor.lastrowid
    finally:
        conexao.close()

    resposta = cliente.get(f"/editar-anotacao/{anotacao_id}")

    assert resposta.status_code == 200
    assert "Anotação original".encode() in resposta.data


def test_editar_anotacao_rejeita_dados_invalidos(cliente):
    conexao = database.conectar()
    try:
        with conexao:
            cursor = conexao.execute("""
                INSERT INTO anotacoes
                    (titulo, materia, conteudo, categoria)
                VALUES (?, ?, ?, ?)
            """, (
                "Título original",
                "Python",
                "Conteúdo original",
                "Programação"
            ))
            anotacao_id = cursor.lastrowid
    finally:
        conexao.close()

    resposta = cliente.post(
        f"/editar-anotacao/{anotacao_id}",
        data={
            "titulo": "",
            "materia": "Python",
            "conteudo": "Conteúdo alterado",
            "categoria": "Programação"
        }
    )

    assert resposta.status_code == 200

    conexao = database.conectar()
    try:
        anotacao = conexao.execute("""
            SELECT titulo, conteudo
            FROM anotacoes
            WHERE id = ?
        """, (anotacao_id,)).fetchone()

        assert anotacao["titulo"] == "Título original"
        assert anotacao["conteudo"] == "Conteúdo original"
    finally:
        conexao.close()


def test_registrar_estudo_rejeita_uuid_invalido(cliente):
    resposta = cliente.post(
        "/registrar-estudo",
        data={
            "materia": "Python",
            "duracao_minutos": "25",
            "identificador": "uuid-invalido"
        },
        follow_redirects=True
    )

    assert resposta.status_code == 200

    conexao = database.conectar()
    try:
        total = conexao.execute("""
            SELECT COUNT(*) FROM sessoes_estudo
        """).fetchone()[0]

        assert total == 0
    finally:
        conexao.close()


def test_definir_meta_rejeita_valor_invalido(cliente):
    resposta = cliente.post(
        "/definir-meta",
        data={"minutos_meta": "0"},
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

        assert meta["minutos_meta"] == 60
    finally:
        conexao.close()


def test_filtrar_anotacoes_por_materia(cliente):
    cliente.post(
        "/nova-anotacao",
        data={
            "titulo": "Estudando Python",
            "materia": "Python",
            "conteudo": "Conteúdo de Python",
            "categoria": "Programação"
        }
    )

    cliente.post(
        "/nova-anotacao",
        data={
            "titulo": "Estudando JavaScript",
            "materia": "JavaScript",
            "conteudo": "Conteúdo de JavaScript",
            "categoria": "Programação"
        }
    )

    resposta = cliente.get(
        "/",
        query_string={"materia": "Python"}
    )

    assert resposta.status_code == 200
    assert b"Estudando Python" in resposta.data
    assert b"Estudando JavaScript" not in resposta.data


def test_filtrar_anotacoes_favoritas(cliente):
    cliente.post(
        "/nova-anotacao",
        data={
            "titulo": "Anotação importante",
            "materia": "Python",
            "conteudo": "Conteúdo favorito",
            "categoria": "Programação"
        }
    )

    cliente.post(
        "/nova-anotacao",
        data={
            "titulo": "Anotação comum",
            "materia": "Python",
            "conteudo": "Conteúdo comum",
            "categoria": "Programação"
        }
    )

    conexao = database.conectar()
    try:
        conexao.execute("""
            UPDATE anotacoes
            SET favorita = 1
            WHERE titulo = ?
        """, ("Anotação importante",))
        conexao.commit()
    finally:
        conexao.close()

    resposta = cliente.get(
        "/",
        query_string={"favoritas": "1"}
    )

    assert resposta.status_code == 200
    assert "Anotação importante".encode("utf-8") in resposta.data
    assert "Anotação comum".encode("utf-8") not in resposta.data

    
from app import validar_texto, validar_inteiro


def test_validar_texto_rejeita_valor_que_nao_e_texto():
    assert validar_texto(None, 100) is None
    assert validar_texto(123, 100) is None


def test_validar_inteiro_rejeita_valor_que_nao_e_texto():
    assert validar_inteiro(None, 1, 1440) is None
    assert validar_inteiro(25, 1, 1440) is None



def test_csrf_bloqueia_post_sem_token(cliente):
    # Ativa a proteção CSRF para este teste
    app.config["WTF_CSRF_ENABLED"] = True

    try:
        # Envia uma requisição sem token CSRF
        resposta = cliente.post(
            "/nova-anotacao",
            data={}
        )

        # O Flask deve rejeitar a requisição
        assert resposta.status_code == 400

    finally:
        # Restaura a configuração usada pelos outros testes
        app.config["WTF_CSRF_ENABLED"] = False