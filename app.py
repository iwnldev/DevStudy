
from flask import Flask, render_template, request, redirect, url_for
from flask_wtf.csrf import CSRFProtect
import os
import uuid
import calendar
from datetime import date
import unicodedata

from database import conexao_aberta, criar_tabelas

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("DEVSTUDY_SECRET_KEY")

csrf = CSRFProtect(app)


# ==========================================
# CONFIGURAÇÕES
# ==========================================

CATEGORIAS = [
    "Programação",
    "Banco de dados",
    "Redes de computadores",
    "Faculdade - ADS",
    "Geral",
    "Outros"
]

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
    """Valida um texto e remove espaços desnecessários."""
    if not isinstance(valor, str):
        return None

    texto = valor.strip()

    if not texto or len(texto) > limite:
        return None

    return texto


def validar_inteiro(valor, minimo, maximo):
    """Converte e valida um número inteiro recebido como texto."""
    if not isinstance(valor, str):
        return None

    valor = valor.strip()

    if not valor or not valor.isdecimal():
        return None

    numero = int(valor)

    if not minimo <= numero <= maximo:
        return None

    return numero


def buscar_materias(conexao):
    """Retorna as matérias cadastradas, em ordem alfabética."""
    return conexao.execute("""
        SELECT id, nome, descricao
        FROM materias
        ORDER BY nome COLLATE NOCASE
    """).fetchall()


def normalizar_nome_materia(nome):
    """Normaliza um nome para comparação sem diferenças de caixa."""
    return unicodedata.normalize("NFC", nome).casefold()


# ==========================================
# MATÉRIAS DE ESTUDO
# ==========================================

@app.route("/materias", methods=["GET", "POST"])
def gerenciar_materias():
    erro = None

    if request.method == "POST":
        nome = validar_texto(
            request.form.get("nome", ""),
            60
        )

        descricao = request.form.get("descricao", "").strip()

        if nome is None:
            erro = "Informe um nome de matéria com até 60 caracteres."

        elif len(descricao) > 300:
            erro = "A descrição deve ter no máximo 300 caracteres."

        else:
            with conexao_aberta() as conexao:
                materias_existentes = conexao.execute("""
                    SELECT id, nome
                    FROM materias
                """).fetchall()

                nome_normalizado = normalizar_nome_materia(nome)

                materia_existente = any(
                    normalizar_nome_materia(materia["nome"])
                    == nome_normalizado
                    for materia in materias_existentes
                )

                if materia_existente:
                    erro = "Já existe uma matéria com esse nome."
                else:
                    conexao.execute("""
                        INSERT INTO materias (nome, descricao)
                        VALUES (?, ?)
                    """, (nome, descricao))

                    return redirect(url_for("gerenciar_materias"))

    with conexao_aberta() as conexao:
        materias = buscar_materias(conexao)

    return render_template(
        "materias.html",
        materias=materias,
        erro=erro
    )


# ==========================================
# CURSOS E MÓDULOS
# ==========================================


@app.route("/cursos")
def listar_cursos():
    """Lista os cursos cadastrados e suas matérias."""
    with conexao_aberta() as conexao:
        cursos = conexao.execute("""
            SELECT
                cursos.id,
                cursos.titulo,
                cursos.descricao,
                cursos.criado_em,
                materias.nome AS materia_nome,
                COUNT(modulos.id) AS total_modulos
            FROM cursos
            LEFT JOIN materias
                ON materias.id = cursos.materia_id
            LEFT JOIN modulos
                ON modulos.curso_id = cursos.id
            GROUP BY cursos.id
            ORDER BY cursos.id DESC
        """).fetchall()

        materias = buscar_materias(conexao)

    return render_template(
        "cursos.html",
        cursos=cursos,
        materias=materias,
        erro=None
    )



@app.route("/novo-curso", methods=["POST"])
def novo_curso():
    """Cadastra um curso e associa uma matéria opcional."""
    titulo = validar_texto(
        request.form.get("titulo", ""),
        120
    )

    descricao = request.form.get("descricao", "").strip()
    materia_id_texto = request.form.get("materia_id", "").strip()

    if titulo is None:
        return redirect(url_for("listar_cursos"))

    if len(descricao) > 1000:
        return redirect(url_for("listar_cursos"))

    materia_id = None

    if materia_id_texto:
        materia_id = validar_inteiro(
            materia_id_texto,
            1,
            2147483647
        )

        if materia_id is None:
            return redirect(url_for("listar_cursos"))

    with conexao_aberta() as conexao:
        if materia_id is not None:
            materia = conexao.execute("""
                SELECT id
                FROM materias
                WHERE id = ?
            """, (materia_id,)).fetchone()

            if materia is None:
                return redirect(url_for("listar_cursos"))

        conexao.execute("""
            INSERT INTO cursos (titulo, descricao, materia_id)
            VALUES (?, ?, ?)
        """, (titulo, descricao, materia_id))

    return redirect(url_for("listar_cursos"))


@app.route("/curso/<int:curso_id>")
def visualizar_curso(curso_id):
    """Exibe os detalhes de um curso e seus módulos."""
    with conexao_aberta() as conexao:
        curso = conexao.execute("""
            SELECT
                cursos.id,
                cursos.titulo,
                cursos.descricao,
                cursos.criado_em,
                materias.nome AS materia_nome
            FROM cursos
            LEFT JOIN materias
                ON materias.id = cursos.materia_id
            WHERE cursos.id = ?
        """, (curso_id,)).fetchone()

        if curso is None:
            return "Curso não encontrado.", 404

        modulos = conexao.execute("""
            SELECT
                id,
                curso_id,
                titulo,
                descricao,
                ordem,
                criado_em
            FROM modulos
            WHERE curso_id = ?
            ORDER BY ordem, id
        """, (curso_id,)).fetchall()

        materias = buscar_materias(conexao)

    return render_template(
        "curso.html",
        curso=curso,
        modulos=modulos,
        materias=materias,
        erro=None
    )


@app.route("/curso/<int:curso_id>/novo-modulo", methods=["POST"])
def novo_modulo(curso_id):
    """Adiciona um módulo a um curso existente."""
    titulo = validar_texto(
        request.form.get("titulo", ""),
        120
    )

    descricao = request.form.get("descricao", "").strip()

    ordem_texto = request.form.get("ordem", "1").strip()
    ordem = validar_inteiro(ordem_texto, 1, 10000)

    if titulo is None or len(descricao) > 1000 or ordem is None:
        return redirect(url_for(
            "visualizar_curso",
            curso_id=curso_id
        ))

    with conexao_aberta() as conexao:
        curso = conexao.execute("""
            SELECT id
            FROM cursos
            WHERE id = ?
        """, (curso_id,)).fetchone()

        if curso is None:
            return "Curso não encontrado.", 404

        conexao.execute("""
            INSERT INTO modulos (
                curso_id,
                titulo,
                descricao,
                ordem
            )
            VALUES (?, ?, ?, ?)
        """, (curso_id, titulo, descricao, ordem))

    return redirect(url_for(
        "visualizar_curso",
        curso_id=curso_id
    ))


@app.route("/modulo/<int:modulo_id>/excluir", methods=["POST"])
def excluir_modulo(modulo_id):
    """Exclui um módulo específico."""
    with conexao_aberta() as conexao:
        modulo = conexao.execute("""
            SELECT curso_id
            FROM modulos
            WHERE id = ?
        """, (modulo_id,)).fetchone()

        if modulo is None:
            return "Módulo não encontrado.", 404

        curso_id = modulo["curso_id"]

        conexao.execute("""
            DELETE FROM modulos
            WHERE id = ?
        """, (modulo_id,))

    return redirect(url_for(
        "visualizar_curso",
        curso_id=curso_id
    ))


# ==========================================
# PÁGINA INICIAL
# ==========================================

@app.route("/")
def inicio():
    pesquisa = request.args.get("pesquisa", "").strip()[:200]
    materia_selecionada = request.args.get("materia", "").strip()
    categoria_selecionada = request.args.get("categoria", "").strip()
    somente_favoritas = request.args.get("favoritas") == "1"

    sql = "SELECT * FROM anotacoes"
    condicoes = []
    parametros = []

    if pesquisa:
        condicoes.append(
            "(titulo LIKE ? OR conteudo LIKE ? OR materia LIKE ?)"
        )
        termo = f"%{pesquisa}%"
        parametros.extend([termo, termo, termo])

    if materia_selecionada:
        condicoes.append("materia = ?")
        parametros.append(materia_selecionada)

    if categoria_selecionada:
        condicoes.append("categoria = ?")
        parametros.append(categoria_selecionada)

    if somente_favoritas:
        condicoes.append("favorita = 1")

    if condicoes:
        sql += " WHERE " + " AND ".join(condicoes)

    sql += " ORDER BY id DESC"

    with conexao_aberta() as conexao:
        anotacoes = conexao.execute(
            sql, parametros
        ).fetchall()

        materias = conexao.execute("""
            SELECT DISTINCT materia
            FROM anotacoes
            ORDER BY materia
        """).fetchall()

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

        meta = conexao.execute("""
            SELECT minutos_meta
            FROM meta_diaria
            WHERE id = 1
        """).fetchone()

        minutos_meta = meta["minutos_meta"] if meta else 60

        minutos_estudados = conexao.execute("""
            SELECT COALESCE(SUM(duracao_minutos), 0)
            FROM sessoes_estudo
            WHERE data_estudo = date('now', 'localtime')
        """).fetchone()[0]

    if minutos_meta > 0:
        progresso = min(
            round(minutos_estudados / minutos_meta * 100),
            100
        )
    else:
        progresso = 0

    minutos_restantes = max(
        minutos_meta - minutos_estudados,
        0
    )

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
    titulo = validar_texto(request.form.get("titulo", ""), 100)
    materia = validar_texto(request.form.get("materia", ""), 60)
    conteudo = validar_texto(request.form.get("conteudo", ""), 10000)
    categoria = validar_texto(request.form.get("categoria", "Geral"), 60)

    if (
        titulo is None
        or materia is None
        or conteudo is None
        or categoria not in CATEGORIAS
    ):
        return redirect(url_for("inicio"))

    with conexao_aberta() as conexao:
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
    materia = validar_texto(request.form.get("materia", ""), 60)

    duracao_texto = request.form.get("duracao_minutos", "")
    identificador_texto = request.form.get("identificador", "").strip()

    if materia not in MATERIAS_ESTUDO:
        return redirect(url_for("inicio"))

    duracao = validar_inteiro(duracao_texto, 1, 1440)

    if duracao is None:
        return redirect(url_for("inicio"))

    try:
        identificador = str(uuid.UUID(identificador_texto))
    except (ValueError, TypeError, AttributeError):
        return redirect(url_for("inicio"))

    with conexao_aberta() as conexao:
        conexao.execute("""
            INSERT INTO sessoes_estudo
                (materia, duracao_minutos, identificador)
            VALUES (?, ?, ?)
            ON CONFLICT(identificador) DO NOTHING
        """, (materia, duracao, identificador))

    return redirect(url_for("inicio"))


# ==========================================
# EDITAR SESSÃO DE ESTUDO
# ==========================================

@app.route("/editar-sessao/<int:id>", methods=["GET", "POST"])
def editar_sessao(id):
    with conexao_aberta() as conexao:
        sessao = conexao.execute("""
            SELECT id, materia, duracao_minutos, data_estudo
            FROM sessoes_estudo
            WHERE id = ?
        """, (id,)).fetchone()

        if sessao is None:
            return "Sessão de estudo não encontrada.", 404

        if request.method == "POST":
            materia = validar_texto(
                request.form.get("materia", ""), 60
            )

            duracao = validar_inteiro(
                request.form.get("duracao_minutos", ""),
                1,
                1440
            )

            if materia not in MATERIAS_ESTUDO or duracao is None:
                return render_template(
                    "editar_sessao.html",
                    sessao=sessao,
                    materias=MATERIAS_ESTUDO,
                    erro="Selecione uma matéria válida e informe uma duração entre 1 e 1440 minutos."
                ), 400

            conexao.execute("""
                UPDATE sessoes_estudo
                SET materia = ?,
                    duracao_minutos = ?
                WHERE id = ?
            """, (materia, duracao, id))

            return redirect(url_for("historico") + "#sessoes")

    return render_template(
        "editar_sessao.html",
        sessao=sessao,
        materias=MATERIAS_ESTUDO,
        erro=None
    )


@app.route("/excluir-sessao/<int:id>", methods=["POST"])
def excluir_sessao(id):
    with conexao_aberta() as conexao:
        sessao = conexao.execute("""
            SELECT id
            FROM sessoes_estudo
            WHERE id = ?
        """, (id,)).fetchone()

        if sessao is None:
            return "Sessão de estudo não encontrada.", 404

        conexao.execute("""
            DELETE FROM sessoes_estudo
            WHERE id = ?
        """, (id,))

    return redirect(url_for("historico") + "#sessoes")


# ==========================================
# DEFINIR META DIÁRIA
# ==========================================

@app.route("/definir-meta", methods=["POST"])
def definir_meta():
    minutos = validar_inteiro(
        request.form.get("minutos_meta", ""),
        1,
        1440
    )

    if minutos is None:
        return redirect(url_for("inicio"))

    with conexao_aberta() as conexao:
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
    with conexao_aberta() as conexao:
        anotacao = conexao.execute("""
            SELECT *
            FROM anotacoes
            WHERE id = ?
        """, (id,)).fetchone()

        if anotacao is None:
            return "Anotação não encontrada.", 404

        if request.method == "POST":
            titulo = validar_texto(request.form.get("titulo", ""), 100)
            materia = validar_texto(request.form.get("materia", ""), 60)
            conteudo = validar_texto(request.form.get("conteudo", ""), 10000)
            categoria = validar_texto(
                request.form.get("categoria", "Geral"), 60
            )

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
    with conexao_aberta() as conexao:
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
    with conexao_aberta() as conexao:
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
    with conexao_aberta() as conexao:
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

        resumo = conexao.execute("""
            SELECT
                COUNT(*) AS total_sessoes,
                COALESCE(SUM(duracao_minutos), 0) AS total_minutos
            FROM sessoes_estudo
        """).fetchone()

        materias_estudadas = conexao.execute("""
            SELECT
                materia,
                COUNT(*) AS total_sessoes,
                SUM(duracao_minutos) AS total_minutos
            FROM sessoes_estudo
            GROUP BY materia
            ORDER BY total_minutos DESC
        """).fetchall()

        estudos_semana = conexao.execute("""
            WITH RECURSIVE semana(data) AS (
                SELECT date('now', 'localtime', '-6 days')

                UNION ALL

                SELECT date(data, '+1 day')
                FROM semana
                WHERE data < date('now', 'localtime')
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

    total_semana = sum(
        dia["total_minutos"] for dia in estudos_semana
    )

    media_diaria = round(total_semana / 7)

    maior_tempo = max(
        (dia["total_minutos"] for dia in estudos_semana),
        default=0
    )

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
# CALENDÁRIO DE ESTUDOS
# ==========================================

@app.route("/calendario")
def calendario():
    hoje_data = date.today()

    try:
        ano = int(request.args.get("ano", hoje_data.year))
        mes = int(request.args.get("mes", hoje_data.month))

        if not 2000 <= ano <= 2100 or not 1 <= mes <= 12:
            raise ValueError

    except (ValueError, TypeError):
        ano = hoje_data.year
        mes = hoje_data.month

    calendario_mes = calendar.Calendar(firstweekday=0)
    semanas = calendario_mes.monthdayscalendar(ano, mes)

    nomes_dias = [
        "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"
    ]

    nome_mes = [
        "Janeiro", "Fevereiro", "Março", "Abril",
        "Maio", "Junho", "Julho", "Agosto",
        "Setembro", "Outubro", "Novembro", "Dezembro"
    ][mes - 1]

    mes_anterior_numero = mes - 1
    ano_anterior = ano

    if mes_anterior_numero == 0:
        mes_anterior_numero = 12
        ano_anterior -= 1

    proximo_mes_numero = mes + 1
    ano_proximo = ano

    if proximo_mes_numero == 13:
        proximo_mes_numero = 1
        ano_proximo += 1

    data_selecionada = None
    valor_data = request.args.get("data", "")

    if valor_data:
        try:
            data_temporaria = date.fromisoformat(valor_data)

            if (
                data_temporaria.year == ano
                and data_temporaria.month == mes
            ):
                data_selecionada = data_temporaria

        except ValueError:
            data_selecionada = None

    with conexao_aberta() as conexao:
        registros = conexao.execute("""
            SELECT
                data_estudo,
                SUM(duracao_minutos) AS minutos,
                COUNT(*) AS sessoes
            FROM sessoes_estudo
            WHERE strftime('%Y-%m', data_estudo) = ?
            GROUP BY data_estudo
            ORDER BY data_estudo
        """, (f"{ano:04d}-{mes:02d}",)).fetchall()

        sessoes_dia = []

        if data_selecionada:
            sessoes_dia = conexao.execute("""
                SELECT
                    id,
                    materia,
                    duracao_minutos,
                    criado_em
                FROM sessoes_estudo
                WHERE data_estudo = ?
                ORDER BY criado_em DESC, id DESC
            """, (data_selecionada.isoformat(),)).fetchall()

    registros_dias = {
        registro["data_estudo"]: {
            "minutos": registro["minutos"],
            "sessoes": registro["sessoes"]
        }
        for registro in registros
    }

    total_mes = sum(
        registro["minutos"] for registro in registros
    )

    dias_estudados = len(registros)

    total_sessoes_mes = sum(
        registro["sessoes"] for registro in registros
    )

    lista_dias = []

    for registro in registros:
        data_registro = date.fromisoformat(
            registro["data_estudo"]
        )

        lista_dias.append({
            "data_formatada": data_registro.strftime("%d/%m/%Y"),
            "minutos": registro["minutos"],
            "sessoes": registro["sessoes"]
        })

    return render_template(
        "calendario.html",
        ano=ano,
        mes=mes,
        nome_mes=nome_mes,
        semanas=semanas,
        nomes_dias=nomes_dias,
        hoje=hoje_data.isoformat(),
        registros_dias=registros_dias,
        total_mes=total_mes,
        dias_estudados=dias_estudados,
        total_sessoes_mes=total_sessoes_mes,
        lista_dias=lista_dias,
        data_selecionada=data_selecionada,
        sessoes_dia=sessoes_dia,
        mes_anterior={
            "ano": ano_anterior,
            "mes": mes_anterior_numero
        },
        proximo_mes={
            "ano": ano_proximo,
            "mes": proximo_mes_numero
        }
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
