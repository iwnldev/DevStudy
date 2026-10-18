
from flask import Flask, render_template, request, redirect, url_for

from database import conectar, criar_tabelas

app = Flask(__name__)

# Categorias disponíveis no DevStudy
CATEGORIAS = [
    "Programação",
    "Banco de dados",
    "Redes de computadores",
    "Faculdade - ADS",
    "Geral",
    "Outros"
]

# Garante que as tabelas existam e estejam atualizadas
criar_tabelas()


@app.route("/")
def inicio():
    # Recebe os filtros da página
    pesquisa = request.args.get("pesquisa", "").strip()
    materia_selecionada = request.args.get("materia", "").strip()
    categoria_selecionada = request.args.get("categoria", "").strip()
    somente_favoritas = request.args.get("favoritas") == "1"

    # Prepara a consulta SQL das anotações
    sql = "SELECT * FROM anotacoes"
    condicoes = []
    parametros = []

    # Pesquisa no título, conteúdo e matéria
    if pesquisa:
        condicoes.append(
            "(titulo LIKE ? OR conteudo LIKE ? OR materia LIKE ?)"
        )
        termo = f"%{pesquisa}%"
        parametros.extend([termo, termo, termo])

    # Filtra pela matéria
    if materia_selecionada:
        condicoes.append("materia = ?")
        parametros.append(materia_selecionada)

    # Filtra pela categoria
    if categoria_selecionada:
        condicoes.append("categoria = ?")
        parametros.append(categoria_selecionada)

    # Filtra somente as favoritas
    if somente_favoritas:
        condicoes.append("favorita = 1")

    # Aplica os filtros à consulta
    if condicoes:
        sql += " WHERE " + " AND ".join(condicoes)

    sql += " ORDER BY id DESC"

    with conectar() as conexao:
        # Busca as anotações conforme os filtros
        anotacoes = conexao.execute(
            sql, parametros
        ).fetchall()

        # Busca as matérias para o filtro
        materias = conexao.execute(
            """
            SELECT DISTINCT materia
            FROM anotacoes
            ORDER BY materia
            """
        ).fetchall()

        # Estatísticas gerais
        total_anotacoes = conexao.execute(
            "SELECT COUNT(*) FROM anotacoes"
        ).fetchone()[0]

        total_materias = conexao.execute(
            "SELECT COUNT(DISTINCT materia) FROM anotacoes"
        ).fetchone()[0]

        total_favoritas = conexao.execute(
            "SELECT COUNT(*) FROM anotacoes WHERE favorita = 1"
        ).fetchone()[0]

        total_categorias = conexao.execute(
            "SELECT COUNT(DISTINCT categoria) FROM anotacoes"
        ).fetchone()[0]

        # Busca a meta diária configurada
        meta = conexao.execute(
            "SELECT minutos_meta FROM meta_diaria WHERE id = 1"
        ).fetchone()

        minutos_meta = meta["minutos_meta"] if meta else 60

        # Soma os minutos estudados hoje
        minutos_estudados = conexao.execute(
            """
            SELECT COALESCE(SUM(duracao_minutos), 0)
            FROM sessoes_estudo
            WHERE data_estudo = date('now', 'localtime')
            """
        ).fetchone()[0]

    # Calcula o progresso da meta
    if minutos_meta > 0:
        progresso = min(
            round(minutos_estudados / minutos_meta * 100),
            100
        )
    else:
        progresso = 0

    # Calcula quantos minutos faltam
    minutos_restantes = max(
        minutos_meta - minutos_estudados,
        0
    )

    # Envia os dados para a página HTML
    return render_template(
        "index.html",
        anotacoes=anotacoes,
        materias=materias,
        categorias=CATEGORIAS,
        pesquisa=pesquisa,
        materia_selecionada=materia_selecionada,
        categoria_selecionada=categoria_selecionada,
        somente_favoritas=somente_favoritas,
        total_anotacoes=total_anotacoes,
        total_materias=total_materias,
        total_favoritas=total_favoritas,
        total_categorias=total_categorias,
        minutos_meta=minutos_meta,
        minutos_estudados=minutos_estudados,
        progresso=progresso,
        minutos_restantes=minutos_restantes
    )


@app.route("/nova-anotacao", methods=["POST"])
def nova_anotacao():
    # Recebe os dados do formulário
    titulo = request.form.get("titulo", "").strip()
    materia = request.form.get("materia", "").strip()
    conteudo = request.form.get("conteudo", "").strip()
    categoria = request.form.get("categoria", "Geral").strip()

    # Valida os dados
    if (
        titulo
        and materia
        and conteudo
        and categoria in CATEGORIAS
    ):
        with conectar() as conexao:
            conexao.execute(
                """
                INSERT INTO anotacoes
                    (titulo, materia, conteudo, categoria)
                VALUES (?, ?, ?, ?)
                """,
                (titulo, materia, conteudo, categoria)
            )

    return redirect(url_for("inicio"))


@app.route("/registrar-estudo", methods=["POST"])
def registrar_estudo():
    # Recebe os dados da sessão
    materia = request.form.get("materia", "").strip()
    duracao_texto = request.form.get("duracao_minutos", "").strip()

    # Valida a duração
    try:
        duracao = int(duracao_texto)
    except (ValueError, TypeError):
        return redirect(url_for("inicio"))

    # Registra sessões de 1 a 1440 minutos
    if materia and 1 <= duracao <= 1440:
        with conectar() as conexao:
            conexao.execute(
                """
                INSERT INTO sessoes_estudo
                    (materia, duracao_minutos)
                VALUES (?, ?)
                """,
                (materia, duracao)
            )

    return redirect(url_for("inicio"))


@app.route("/definir-meta", methods=["POST"])
def definir_meta():
    # Recebe a nova meta diária
    minutos_texto = request.form.get("minutos_meta", "").strip()

    try:
        minutos = int(minutos_texto)
    except (ValueError, TypeError):
        return redirect(url_for("inicio"))

    # Aceita metas de 1 a 1440 minutos
    if 1 <= minutos <= 1440:
        with conectar() as conexao:
            conexao.execute(
                """
                INSERT INTO meta_diaria (id, minutos_meta)
                VALUES (1, ?)
                ON CONFLICT(id)
                DO UPDATE SET minutos_meta = excluded.minutos_meta
                """,
                (minutos,)
            )

    return redirect(url_for("inicio"))


@app.route("/editar-anotacao/<int:id>", methods=["GET", "POST"])
def editar_anotacao(id):
    with conectar() as conexao:
        # Busca a anotação
        anotacao = conexao.execute(
            "SELECT * FROM anotacoes WHERE id = ?",
            (id,)
        ).fetchone()

        if anotacao is None:
            return "Anotação não encontrada.", 404

        # Atualiza a anotação quando o formulário é enviado
        if request.method == "POST":
            titulo = request.form.get("titulo", "").strip()
            materia = request.form.get("materia", "").strip()
            conteudo = request.form.get("conteudo", "").strip()
            categoria = request.form.get("categoria", "Geral").strip()

            if (
                titulo
                and materia
                and conteudo
                and categoria in CATEGORIAS
            ):
                conexao.execute(
                    """
                    UPDATE anotacoes
                    SET titulo = ?,
                        materia = ?,
                        conteudo = ?,
                        categoria = ?
                    WHERE id = ?
                    """,
                    (titulo, materia, conteudo, categoria, id)
                )

                return redirect(url_for("inicio"))

    return render_template(
        "editar.html",
        anotacao=anotacao,
        categorias=CATEGORIAS
    )


@app.route("/excluir-anotacao/<int:id>", methods=["POST"])
def excluir_anotacao(id):
    with conectar() as conexao:
        conexao.execute(
            "DELETE FROM anotacoes WHERE id = ?",
            (id,)
        )

    return redirect(url_for("inicio"))


@app.route("/favoritar-anotacao/<int:id>", methods=["POST"])
def favoritar_anotacao(id):
    with conectar() as conexao:
        anotacao = conexao.execute(
            "SELECT favorita FROM anotacoes WHERE id = ?",
            (id,)
        ).fetchone()

        if anotacao is not None:
            novo_estado = 0 if anotacao["favorita"] == 1 else 1

            conexao.execute(
                "UPDATE anotacoes SET favorita = ? WHERE id = ?",
                (novo_estado, id)
            )

    return redirect(url_for("inicio"))



@app.route("/historico")
def historico():
    with conectar() as conexao:
        # Busca todas as sessões registradas
        sessoes = conexao.execute("""
            SELECT id, materia, duracao_minutos, data_estudo, criado_em
            FROM sessoes_estudo
            ORDER BY data_estudo DESC, id DESC
        """).fetchall()

        # Estatísticas gerais de todo o histórico
        resumo = conexao.execute("""
            SELECT
                COUNT(*) AS total_sessoes,
                COALESCE(SUM(duracao_minutos), 0) AS total_minutos
            FROM sessoes_estudo
        """).fetchone()

        # Tempo estudado em cada matéria
        materias_estudadas = conexao.execute("""
            SELECT
                materia,
                COUNT(*) AS total_sessoes,
                SUM(duracao_minutos) AS total_minutos
            FROM sessoes_estudo
            GROUP BY materia
            ORDER BY total_minutos DESC
        """).fetchall()

        # Cria os sete dias da semana atual, de segunda a domingo.
        # Dias sem registros também aparecem, com zero minutos.
        estudos_semana = conexao.execute("""
            WITH RECURSIVE semana(data) AS (
                SELECT date('now', 'localtime', 'weekday 0', '-6 days')

                UNION ALL

                SELECT date(data, '+1 day')
                FROM semana
                WHERE data < date(
                    'now', 'localtime', 'weekday 0'
                )
            )
            SELECT
                semana.data AS data_estudo,
                CASE strftime('%w', semana.data)
                    WHEN '1' THEN 'Segunda'
                    WHEN '2' THEN 'Terça'
                    WHEN '3' THEN 'Quarta'
                    WHEN '4' THEN 'Quinta'
                    WHEN '5' THEN 'Sexta'
                    WHEN '6' THEN 'Sábado'
                    WHEN '0' THEN 'Domingo'
                END AS dia_nome,
                COALESCE(SUM(sessoes_estudo.duracao_minutos), 0)
                    AS total_minutos
            FROM semana
            LEFT JOIN sessoes_estudo
                ON sessoes_estudo.data_estudo = semana.data
            GROUP BY semana.data
            ORDER BY semana.data
        """).fetchall()

    # Calcula os indicadores da semana
    total_semana = sum(
        dia["total_minutos"] for dia in estudos_semana
    )

    media_diaria = round(total_semana / 7)

    maior_tempo = max(
        (dia["total_minutos"] for dia in estudos_semana),
        default=0
    )

    # Identifica o dia com mais minutos estudados
    melhor_dia = max(
        estudos_semana,
        key=lambda dia: dia["total_minutos"],
        default=None
    )

    return render_template(
        "historico.html",
        sessoes=sessoes,
        resumo=resumo,
        materias_estudadas=materias_estudadas,
        estudos_semana=estudos_semana,
        total_semana=total_semana,
        media_diaria=media_diaria,
        maior_tempo=maior_tempo,
        melhor_dia=melhor_dia
    )

if __name__ == "__main__":
    app.run(debug=True)
