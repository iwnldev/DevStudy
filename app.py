
from flask import Flask, render_template, request, redirect, url_for
from flask_wtf.csrf import CSRFProtect
import os
import uuid

from database import conectar, criar_tabelas

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("DEVSTUDY_SECRET_KEY")

csrf = CSRFProtect(app)

# ==========================================
# CONFIGURAÇÕES
# ==========================================

# Categorias disponíveis no DevStudy
CATEGORIAS = [
    "Programação",
    "Banco de dados",
    "Redes de computadores",
    "Faculdade - ADS",
    "Geral",
    "Outros"
]

# Matérias permitidas para registrar sessões de estudo
MATERIAS_ESTUDO = [
    "Python",
    "JavaScript",
    "Banco de dados",
    "Redes de computadores",
    "Faculdade - ADS",
    "Geral"
]


# ==========================================
# FUNÇÕES DE VALIDAÇÃO
# ==========================================

def validar_texto(valor, limite):
    """
    Remove espaços desnecessários e verifica
    se o texto está preenchido e dentro do limite.
    """
    if not isinstance(valor, str):
        return None

    texto = valor.strip()

    if not texto:
        return None

    if len(texto) > limite:
        return None

    return texto


def validar_inteiro(valor, minimo, maximo):
    """
    Converte um valor para inteiro e verifica
    se está dentro do intervalo permitido.
    """
    if not isinstance(valor, str):
        return None

    valor = valor.strip()

    if not valor or not valor.isdecimal():
        return None

    numero = int(valor)

    if not minimo <= numero <= maximo:
        return None

    return numero

# ==========================================
# PÁGINA INICIAL
# ==========================================

@app.route("/")
def inicio():
    # Recebe os filtros da página
    pesquisa = request.args.get("pesquisa", "").strip()
    materia_selecionada = request.args.get("materia", "").strip()
    categoria_selecionada = request.args.get("categoria", "").strip()
    somente_favoritas = request.args.get("favoritas") == "1"

    # Limita o tamanho da pesquisa
    pesquisa = pesquisa[:200]

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
        materias = conexao.execute("""
            SELECT DISTINCT materia
            FROM anotacoes
            ORDER BY materia
        """).fetchall()

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
        meta = conexao.execute("""
            SELECT minutos_meta
            FROM meta_diaria
            WHERE id = 1
        """).fetchone()

        minutos_meta = meta["minutos_meta"] if meta else 60

        # Soma os minutos estudados hoje
        minutos_estudados = conexao.execute("""
            SELECT COALESCE(SUM(duracao_minutos), 0)
            FROM sessoes_estudo
            WHERE data_estudo = date('now', 'localtime')
        """).fetchone()[0]

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


# ==========================================
# CADASTRAR ANOTAÇÃO
# ==========================================

@app.route("/nova-anotacao", methods=["POST"])
def nova_anotacao():
    # Recebe e valida os dados do formulário
    titulo = validar_texto(
        request.form.get("titulo", ""),
        100
    )

    materia = validar_texto(
        request.form.get("materia", ""),
        60
    )

    conteudo = validar_texto(
        request.form.get("conteudo", ""),
        10000
    )

    categoria = validar_texto(
        request.form.get("categoria", "Geral"),
        60
    )

    # Verifica se todos os campos são válidos
    if (
        titulo is None
        or materia is None
        or conteudo is None
        or categoria not in CATEGORIAS
    ):
        return redirect(url_for("inicio"))

    # Salva a anotação no banco de dados
    with conectar() as conexao:
        conexao.execute("""
            INSERT INTO anotacoes
                (titulo, materia, conteudo, categoria)
            VALUES (?, ?, ?, ?)
        """, (titulo, materia, conteudo, categoria))

    return redirect(url_for("inicio"))


# ==========================================
# REGISTRAR SESSÃO DE ESTUDO
# ==========================================

@app.route("/registrar-estudo", methods=["POST"])
def registrar_estudo():
    # Recebe os dados enviados pelo formulário
    materia = validar_texto(
        request.form.get("materia", ""),
        60
    )

    duracao_texto = request.form.get(
        "duracao_minutos", ""
    )

    identificador_texto = request.form.get(
        "identificador", ""
    ).strip()

    # Valida a matéria
    if materia not in MATERIAS_ESTUDO:
        return redirect(url_for("inicio"))

    # Converte e valida a duração
    duracao = validar_inteiro(
        duracao_texto,
        1,
        1440
    )

    if duracao is None:
        return redirect(url_for("inicio"))

    # Verifica se o identificador tem formato UUID válido
    try:
        identificador = str(uuid.UUID(identificador_texto))
    except (ValueError, TypeError, AttributeError):
        return redirect(url_for("inicio"))

    # Salva a sessão sem repetir o mesmo identificador
    with conectar() as conexao:
        conexao.execute("""
            INSERT INTO sessoes_estudo
                (materia, duracao_minutos, identificador)
            VALUES (?, ?, ?)
            ON CONFLICT(identificador) DO NOTHING
        """, (materia, duracao, identificador))

    return redirect(url_for("inicio"))


# ==========================================
# DEFINIR META DIÁRIA
# ==========================================

@app.route("/definir-meta", methods=["POST"])
def definir_meta():
    # Recebe e valida a nova meta diária
    minutos = validar_inteiro(
        request.form.get("minutos_meta", ""),
        1,
        1440
    )

    if minutos is None:
        return redirect(url_for("inicio"))

    with conectar() as conexao:
        conexao.execute("""
            INSERT INTO meta_diaria (id, minutos_meta)
            VALUES (1, ?)
            ON CONFLICT(id)
            DO UPDATE SET minutos_meta = excluded.minutos_meta
        """, (minutos,))

    return redirect(url_for("inicio"))


# ==========================================
# EDITAR ANOTAÇÃO
# ==========================================

@app.route("/editar-anotacao/<int:id>", methods=["GET", "POST"])
def editar_anotacao(id):
    with conectar() as conexao:
        # Busca a anotação
        anotacao = conexao.execute("""
            SELECT *
            FROM anotacoes
            WHERE id = ?
        """, (id,)).fetchone()

        if anotacao is None:
            return "Anotação não encontrada.", 404

        # Atualiza a anotação quando o formulário é enviado
        if request.method == "POST":
            titulo = validar_texto(
                request.form.get("titulo", ""),
                100
            )

            materia = validar_texto(
                request.form.get("materia", ""),
                60
            )

            conteudo = validar_texto(
                request.form.get("conteudo", ""),
                10000
            )

            categoria = validar_texto(
                request.form.get("categoria", "Geral"),
                60
            )

            # Só atualiza se todos os campos forem válidos
            if (
                titulo is not None
                and materia is not None
                and conteudo is not None
                and categoria in CATEGORIAS
            ):
                conexao.execute("""
                    UPDATE anotacoes
                    SET titulo = ?,
                        materia = ?,
                        conteudo = ?,
                        categoria = ?
                    WHERE id = ?
                """, (titulo, materia, conteudo, categoria, id))

                return redirect(url_for("inicio"))

    return render_template(
        "editar.html",
        anotacao=anotacao,
        categorias=CATEGORIAS
    )


# ==========================================
# EXCLUIR ANOTAÇÃO
# ==========================================

@app.route("/excluir-anotacao/<int:id>", methods=["POST"])
def excluir_anotacao(id):
    with conectar() as conexao:
        conexao.execute("""
            DELETE FROM anotacoes
            WHERE id = ?
        """, (id,))

    return redirect(url_for("inicio"))


# ==========================================
# FAVORITAR ANOTAÇÃO
# ==========================================

@app.route("/favoritar-anotacao/<int:id>", methods=["POST"])
def favoritar_anotacao(id):
    with conectar() as conexao:
        anotacao = conexao.execute("""
            SELECT favorita
            FROM anotacoes
            WHERE id = ?
        """, (id,)).fetchone()

        if anotacao is not None:
            novo_estado = 0 if anotacao["favorita"] == 1 else 1

            conexao.execute("""
                UPDATE anotacoes
                SET favorita = ?
                WHERE id = ?
            """, (novo_estado, id))

    return redirect(url_for("inicio"))


# ==========================================
# HISTÓRICO DE ESTUDOS
# ==========================================

@app.route("/historico")
def historico():
    with conectar() as conexao:
        # Busca todas as sessões registradas
        sessoes = conexao.execute("""
            SELECT
                id,
                materia,
                duracao_minutos,
                data_estudo,
                criado_em
            FROM sessoes_estudo
            ORDER BY data_estudo DESC, id DESC
        """).fetchall()

        # Estatísticas gerais do histórico
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

        # Cria os sete dias da semana atual
        # Dias sem registros também aparecem com zero minutos
        estudos_semana = conexao.execute("""
            WITH RECURSIVE semana(data) AS (
                SELECT date(
                    'now', 'localtime', 'weekday 0', '-6 days'
                )

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
                COALESCE(
                    SUM(sessoes_estudo.duracao_minutos), 0
                ) AS total_minutos
            FROM semana
            LEFT JOIN sessoes_estudo
                ON sessoes_estudo.data_estudo = semana.data
            GROUP BY semana.data
            ORDER BY semana.data
        """).fetchall()

    # Calcula os indicadores semanais
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



# ==========================================
# EXECUTAR A APLICAÇÃO
# ==========================================

if __name__ == "__main__":
    if not app.config["SECRET_KEY"]:
        raise RuntimeError(
            "A variável DEVSTUDY_SECRET_KEY não está configurada. "
            "Configure a chave antes de iniciar o aplicativo."
        )

    criar_tabelas()

    app.run(
        debug=os.environ.get("FLASK_DEBUG") == "1"
    )

