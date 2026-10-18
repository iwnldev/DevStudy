
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
