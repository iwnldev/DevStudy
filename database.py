
import sqlite3
import json
import os
from pathlib import Path
from contextlib import contextmanager
import unicodedata
from contextvars import ContextVar


# ==========================================
# CONFIGURAÇÃO DO BANCO DE DADOS
# ==========================================

PASTA_PROJETO = Path(__file__).resolve().parent

PASTA_DADOS = Path(os.environ.get("DEVSTUDY_DATA_DIR", PASTA_PROJETO / "instance")).resolve()
PASTA_DADOS.mkdir(parents=True, exist_ok=True)

CAMINHO_BANCO = PASTA_DADOS / "devstudy.db"
CAMINHO_CONTAS = PASTA_DADOS / "contas.db"
_USUARIO_BANCO_ATUAL = ContextVar("devstudy_usuario_banco", default=None)


def definir_usuario_banco(usuario_id):
    """Seleciona o banco privado deste usuário durante a requisição atual."""
    usuario_id = int(usuario_id)
    if usuario_id < 1:
        raise ValueError("Identificador de usuário inválido.")
    return _USUARIO_BANCO_ATUAL.set(usuario_id)


def restaurar_usuario_banco(token):
    _USUARIO_BANCO_ATUAL.reset(token)


def caminho_banco_atual():
    usuario_id = _USUARIO_BANCO_ATUAL.get()
    if usuario_id is None:
        return Path(CAMINHO_BANCO)
    pasta_usuarios = PASTA_DADOS / "usuarios"
    pasta_usuarios.mkdir(parents=True, exist_ok=True)
    return pasta_usuarios / f"usuario_{usuario_id}.db"


def inicializar_contas():
    """Cria o armazenamento separado de credenciais e limites da IA."""
    Path(CAMINHO_CONTAS).parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(CAMINHO_CONTAS)
    try:
        conexao.execute("PRAGMA foreign_keys = ON")
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                senha_hash TEXT NOT NULL,
                email_verificado INTEGER NOT NULL DEFAULT 0,
                senha_atualizada_em TEXT NOT NULL DEFAULT '',
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        colunas_usuarios = {coluna[1] for coluna in conexao.execute("PRAGMA table_info(usuarios)")}
        if "email_verificado" not in colunas_usuarios:
            conexao.execute("ALTER TABLE usuarios ADD COLUMN email_verificado INTEGER NOT NULL DEFAULT 0")
        if "senha_atualizada_em" not in colunas_usuarios:
            conexao.execute("ALTER TABLE usuarios ADD COLUMN senha_atualizada_em TEXT NOT NULL DEFAULT ''")
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS uso_tutor_ia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                usado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
                    ON DELETE CASCADE
            )
        """)
        conexao.execute("""
            CREATE INDEX IF NOT EXISTS idx_uso_ia_usuario_data
            ON uso_tutor_ia (usuario_id, usado_em)
        """)
        conexao.commit()
    finally:
        conexao.close()


def conectar_contas():
    conexao = sqlite3.connect(CAMINHO_CONTAS, timeout=10)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def criar_banco_usuario(usuario_id):
    """Copia a base curricular para um banco privado, uma única vez."""
    usuario_id = int(usuario_id)
    destino = PASTA_DADOS / "usuarios" / f"usuario_{usuario_id}.db"
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        return destino

    origem = Path(CAMINHO_BANCO)
    if origem.exists():
        with sqlite3.connect(origem) as fonte, sqlite3.connect(destino) as copia:
            fonte.backup(copia)
    else:
        sqlite3.connect(destino).close()
    return destino


def popular_conteudo_inicial():
    """Insere uma coleção inicial autoral, com fontes públicas para aprofundar."""
    from conteudo_inicial_ads import CONTEUDOS

    with conexao_aberta() as conexao:
        conexao.execute("""CREATE TABLE IF NOT EXISTS migracoes_aplicadas (
            versao TEXT PRIMARY KEY, aplicado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        versao = "conteudo_aberto_ads_v1"
        ja_inserido = conexao.execute("SELECT 1 FROM migracoes_aplicadas WHERE versao = ?", (versao,)).fetchone()
        if not ja_inserido:
            for item in CONTEUDOS:
                materia = conexao.execute("SELECT id FROM materias WHERE nome = ?", (item["materia"],)).fetchone()
                if materia is None:
                    continue
                materia_id = materia["id"]
                conexao.execute("""INSERT INTO materiais_estudo
                    (materia_id, titulo, tipo, conteudo, link, autor, licenca, validado)
                    VALUES (?, ?, 'resumo', ?, ?, ?, ?, 0)""",
                    (materia_id, "Guia inicial (sugestão)", item["resumo"], item["url"], item["fonte"],
                     "Resumo autoral DevStudy; consulte a fonte original e seus termos de uso."))
                conexao.execute("""INSERT INTO questoes
                    (materia_id, enunciado, tipo, alternativas, resposta_correta, explicacao, dificuldade)
                    VALUES (?, ?, 'multipla_escolha', ?, ?, ?, 'facil')""",
                    (materia_id, item["pergunta"], json.dumps(item["alternativas"], ensure_ascii=False),
                     str(item["correta"]), item["explicacao"]))
                for frente, verso in item["cards"]:
                    conexao.execute("INSERT INTO flashcards (materia_id, frente, verso) VALUES (?, ?, ?)",
                                    (materia_id, frente, verso))
            conexao.execute("INSERT INTO migracoes_aplicadas (versao) VALUES (?)", (versao,))


def popular_aulas_praticas():
    """Troca os placeholders da trilha por aulas explicativas e projetos reais."""
    from conteudo_inicial_ads import CONTEUDOS, PROJETOS
    versao = "aulas_praticas_ads_v1"
    with conexao_aberta() as conexao:
        if conexao.execute("SELECT 1 FROM migracoes_aplicadas WHERE versao = ?", (versao,)).fetchone():
            return
        aulas_antigas = {
            1: "Comece pelo resumo inicial da disciplina. Anote 3 conceitos, defina cada um com suas palavras e abra a fonte oficial vinculada ao material.",
            2: "Resolva o exercício da disciplina sem consultar o gabarito. Depois compare seu raciocínio com a explicação e revise os flashcards.",
        }
        for item in CONTEUDOS:
            materia = conexao.execute("SELECT id FROM materias WHERE nome = ?", (item["materia"],)).fetchone()
            if not materia:
                continue
            curso = conexao.execute("""SELECT id FROM cursos
                WHERE materia_id = ? AND titulo IN (?, ?) ORDER BY id DESC LIMIT 1""",
                (materia["id"], f"Trilha de estudo: {item['materia']}", f"Trilha inicial: {item['materia']}")).fetchone()
            if not curso:
                continue
            modulos = conexao.execute("SELECT id, ordem FROM modulos WHERE curso_id = ? ORDER BY ordem", (curso["id"],)).fetchall()
            modulos_por_ordem = {modulo["ordem"]: modulo["id"] for modulo in modulos}
            fonte = item["url"]
            conteudos = {
                1: (
                    f"AULA 1 — CONCEITOS ESSENCIAIS\n\n{item['resumo']}\n\n"
                    "ROTEIRO DE ESTUDO\n"
                    "1. Leia o texto uma vez para entender a ideia geral.\n"
                    "2. Anote os termos técnicos e escreva uma definição com suas palavras.\n"
                    "3. Dê um exemplo próprio para cada conceito e compare com a fonte indicada.\n"
                    "4. Explique o tema em voz alta sem consultar suas anotações.\n\n"
                    f"FONTE PARA APROFUNDAR\n{fonte}\n\n"
                    "CHECAGEM\nQuais são as três ideias principais? Que exemplo real mostra cada uma? O que ainda ficou confuso?"
                ),
                2: (
                    f"AULA 2 — EXEMPLO RESOLVIDO E PRÁTICA\n\n"
                    f"QUESTÃO\n{item['pergunta']}\n\n"
                    + "\n".join(f"{letra}) {alternativa}" for letra, alternativa in zip("ABCD", item["alternativas"]))
                    + f"\n\nRESOLUÇÃO COMENTADA\n{item['explicacao']}\n"
                    "Primeiro identifique o conceito que a pergunta avalia. Depois compare cada alternativa com a definição estudada e elimine as que descrevem outra função ou camada. Por fim, justifique a escolha sem depender apenas de memorizar a letra.\n\n"
                    f"GABARITO: {('ABCD'[item['correta'] - 1])}) {item['alternativas'][item['correta'] - 1]}\n\n"
                    f"REVISÃO ATIVA\nPergunta: {item['cards'][0][0]}\nResposta esperada: {item['cards'][0][1]}\n\n"
                    "Tente responder antes de ler a resposta e depois explique o raciocínio em uma frase."
                ),
                3: (
                    f"AULA 3 — PROJETO PRÁTICO\n\n{PROJETOS[item['materia']]}\n\n"
                    "COMO EXECUTAR\n"
                    "1. Escreva o problema e o resultado esperado antes de começar.\n"
                    "2. Divida a tarefa em etapas pequenas e implemente uma de cada vez.\n"
                    "3. Registre decisões, testes realizados e erros encontrados.\n"
                    "4. Revise a solução usando os conceitos e a fonte desta disciplina.\n\n"
                    "ENTREGA E AUTOAVALIAÇÃO\nGuarde o artefato produzido, explique duas decisões técnicas e indique uma melhoria futura. Você consegue ensinar a solução a outra pessoa? Se não, volte ao conceito que ainda precisa de revisão."
                ),
            }
            for ordem, modulo_id in modulos_por_ordem.items():
                if ordem not in conteudos:
                    continue
                aula = conexao.execute("SELECT id, conteudo FROM aulas WHERE modulo_id = ? ORDER BY ordem, id LIMIT 1", (modulo_id,)).fetchone()
                if not aula:
                    continue
                conteudo_antigo = aulas_antigas.get(ordem)
                if ordem == 3:
                    conteudo_antigo = f"Crie um exemplo ou pequeno projeto aplicado a {item['materia']}. Registre os passos, as decisões, o que aprendeu e uma dúvida para pesquisar."
                if aula["conteudo"] == conteudo_antigo:
                    conexao.execute("UPDATE aulas SET conteudo = ? WHERE id = ?", (conteudos[ordem], aula["id"]))
        conexao.execute("INSERT INTO migracoes_aplicadas (versao) VALUES (?)", (versao,))

    with conexao_aberta() as conexao:
        versao = "trilhas_rotulo_disciplina_v2"
        if not conexao.execute("SELECT 1 FROM migracoes_aplicadas WHERE versao = ?", (versao,)).fetchone():
            conexao.execute("""UPDATE cursos
                SET titulo = 'Trilha de estudo: ' || (
                    SELECT nome FROM materias WHERE materias.id = cursos.materia_id
                )
                WHERE cursos.materia_id IS NOT NULL
                    AND cursos.titulo LIKE 'Trilha inicial: %'""")
            conexao.execute("INSERT INTO migracoes_aplicadas (versao) VALUES (?)", (versao,))

    # Trilha progressiva em três etapas, separada do resumo e das fontes.
    from conteudo_inicial_ads import TRILHAS
    with conexao_aberta() as conexao:
        versao = "trilhas_progressivas_ads_v1"
        if conexao.execute("SELECT 1 FROM migracoes_aplicadas WHERE versao = ?", (versao,)).fetchone():
            return
        for nome_materia, etapas in TRILHAS.items():
            materia = conexao.execute("SELECT id FROM materias WHERE nome = ?", (nome_materia,)).fetchone()
            if not materia:
                continue
            curso_id = conexao.execute("""INSERT INTO cursos (titulo, descricao, materia_id)
                VALUES (?, ?, ?)""", (f"Trilha de estudo: {nome_materia}",
                "Roteiro progressivo sugerido; ajuste conforme a ementa e o ritmo da turma.", materia["id"])).lastrowid
            for ordem, titulo in enumerate(etapas, start=1):
                modulo_id = conexao.execute("""INSERT INTO modulos (curso_id, titulo, descricao, ordem)
                    VALUES (?, ?, ?, ?)""", (curso_id, titulo, "Leia o guia da disciplina, consulte a fonte indicada e registre dúvidas.", ordem)).lastrowid
                if ordem == 1:
                    aula_titulo = "Leitura guiada e conceitos essenciais"
                    conteudo = "Comece pelo resumo inicial da disciplina. Anote 3 conceitos, defina cada um com suas palavras e abra a fonte oficial vinculada ao material."
                elif ordem == 2:
                    aula_titulo = "Prática e verificação do entendimento"
                    conteudo = "Resolva o exercício da disciplina sem consultar o gabarito. Depois compare seu raciocínio com a explicação e revise os flashcards."
                else:
                    aula_titulo = "Aplicação, revisão e reflexão"
                    conteudo = f"Crie um exemplo ou pequeno projeto aplicado a {nome_materia}. Registre os passos, as decisões, o que aprendeu e uma dúvida para pesquisar."
                conexao.execute("INSERT INTO aulas (modulo_id, titulo, conteudo, ordem) VALUES (?, ?, ?, 1)",
                                (modulo_id, aula_titulo, conteudo))
        conexao.execute("INSERT INTO migracoes_aplicadas (versao) VALUES (?)", (versao,))


def popular_aulas_didaticas():
    """Substitui os resumos curtos por aulas completas, sem sobrescrever aulas próprias."""
    from aulas_ads import AULAS
    from conteudo_inicial_ads import CONTEUDOS

    versao = "aulas_didaticas_ads_v1"
    conteudos_por_materia = {item["materia"]: item for item in CONTEUDOS}
    prefixos_gerados = (
        "AULA 1 — CONCEITOS ESSENCIAIS",
        "AULA 2 — EXEMPLO RESOLVIDO E PRÁTICA",
        "AULA 3 — PROJETO PRÁTICO",
    )

    with conexao_aberta() as conexao:
        if conexao.execute(
            "SELECT 1 FROM migracoes_aplicadas WHERE versao = ?", (versao,)
        ).fetchone():
            return

        for nome_materia, etapas in AULAS.items():
            materia = conexao.execute(
                "SELECT id FROM materias WHERE nome = ?", (nome_materia,)
            ).fetchone()
            referencia = conteudos_por_materia.get(nome_materia)
            if not materia or not referencia:
                continue

            curso = conexao.execute(
                """SELECT id FROM cursos
                   WHERE materia_id = ? AND titulo IN (?, ?)
                   ORDER BY id DESC LIMIT 1""",
                (materia["id"], f"Trilha de estudo: {nome_materia}",
                 f"Trilha inicial: {nome_materia}"),
            ).fetchone()
            if not curso:
                continue

            for ordem, etapa in enumerate(etapas, start=1):
                modulo = conexao.execute(
                    "SELECT id FROM modulos WHERE curso_id = ? AND ordem = ?",
                    (curso["id"], ordem),
                ).fetchone()
                if not modulo:
                    continue
                aula = conexao.execute(
                    """SELECT id, conteudo FROM aulas
                       WHERE modulo_id = ? ORDER BY ordem, id LIMIT 1""",
                    (modulo["id"],),
                ).fetchone()
                if not aula or not (aula["conteudo"] or "").startswith(prefixos_gerados):
                    continue

                numero = f"{ordem:02d}"
                conteudo = (
                    f"## Aula {numero} — {etapa['titulo']}\n\n"
                    f"### O que você vai aprender\nAo final, você deverá conseguir explicar {etapa['titulo'].lower()}, aplicar a ideia ao exemplo e resolver uma situação semelhante por conta própria.\n\n"
                    f"### Explicação passo a passo\n{etapa['explicacao']}\n\n"
                    f"### Exemplo trabalhado\n{etapa['exemplo']}\n\n"
                    f"### Pratique antes de olhar o gabarito\n{etapa['exercicio']}\n\n"
                    f"### Gabarito comentado\n{etapa['gabarito']}\n\n"
                    f"### Fonte pública para continuar\n{referencia['fonte']}: {referencia['url']}\n\n"
                    "### Fechamento\nExplique o conceito principal com suas palavras e anote uma dúvida concreta. Se não conseguir justificar a resposta, volte à explicação e refaça o exemplo sem copiar os passos."
                )
                conexao.execute(
                    "UPDATE aulas SET titulo = ?, conteudo = ? WHERE id = ?",
                    (etapa["titulo"], conteudo, aula["id"]),
                )

        conexao.execute(
            "INSERT INTO migracoes_aplicadas (versao) VALUES (?)", (versao,)
        )


def popular_aulas_aprofundamento():
    """Adiciona uma aula autoral prática a cada módulo das 23 disciplinas."""
    from aulas_aprofundamento import APROFUNDAMENTO
    from conteudo_inicial_ads import CONTEUDOS

    versao = "aprofundamento_ads_v1"
    referencias = {item["materia"]: item for item in CONTEUDOS}

    with conexao_aberta() as conexao:
        if conexao.execute(
            "SELECT 1 FROM migracoes_aplicadas WHERE versao = ?", (versao,)
        ).fetchone():
            return

        for materia_nome, aulas_extra in APROFUNDAMENTO.items():
            materia = conexao.execute(
                "SELECT id FROM materias WHERE nome = ?", (materia_nome,)
            ).fetchone()
            referencia = referencias.get(materia_nome)
            if not materia or not referencia:
                continue
            curso = conexao.execute(
                """SELECT id FROM cursos
                   WHERE materia_id = ? AND titulo IN (?, ?)
                   ORDER BY id DESC LIMIT 1""",
                (materia["id"], f"Trilha de estudo: {materia_nome}",
                 f"Trilha inicial: {materia_nome}"),
            ).fetchone()
            if not curso:
                continue

            modulos = conexao.execute(
                "SELECT id, ordem FROM modulos WHERE curso_id = ? ORDER BY ordem, id",
                (curso["id"],),
            ).fetchall()
            por_ordem = {modulo["ordem"]: modulo["id"] for modulo in modulos}
            for ordem, item in enumerate(aulas_extra, start=1):
                modulo_id = por_ordem.get(ordem)
                if modulo_id is None:
                    continue
                ultima_ordem = conexao.execute(
                    "SELECT COALESCE(MAX(ordem), 0) FROM aulas WHERE modulo_id = ?",
                    (modulo_id,),
                ).fetchone()[0]
                conteudo = (
                    f"## {item['titulo']}\n\n"
                    f"### Conceitos e aprofundamento\n{item['explicacao']}\n\n"
                    f"### Caso aplicado\n{item['exemplo']}\n\n"
                    f"### Desafio\nTente resolver sem consultar a resposta. Registre qual regra ou conceito usou.\n{item['exercicio']}\n\n"
                    f"### Resolução comentada\n{item['gabarito']}\n\n"
                    f"### Leitura de referência\n{referencia['fonte']}: {referencia['url']}\n\n"
                    "### Para consolidar\nExplique por que a solução funciona e em que cenário ela deixaria de funcionar. Depois aplique o mesmo raciocínio a um exemplo próprio da disciplina."
                )
                conexao.execute(
                    "INSERT INTO aulas (modulo_id, titulo, conteudo, ordem) VALUES (?, ?, ?, ?)",
                    (modulo_id, item["titulo"], conteudo, ultima_ordem + 1),
                )

        conexao.execute(
            "INSERT INTO migracoes_aplicadas (versao) VALUES (?)", (versao,)
        )

# ==========================================
# MATÉRIAS INICIAIS
# ==========================================

MATERIAS_INICIAIS = [
    "Banco de Dados",
    "Matemática Aplicada à Informática",
    "Projeto Integrador: Introdução à Linguagem de Programação",
    "Sistemas Operacionais",
    "Tecnologias da Computação",
    "Comunicação Profissional",
    "Algoritmo e Estrutura de Dados",
    "Análise e Modelagem de Sistemas",
    "Programação Front-End",
    "Projeto Integrador: Arquitetura de Computadores",
    "Debates Contemporâneos",
    "Programação Orientada a Objeto",
    "Projeto Integrador: Engenharia de Software",
    "Redes de Computadores e Segurança da Informação",
    "Tecnologias da Web",
    "Desenvolvimento de Jogos",
    "Desenvolvimento e Sustentabilidade",
    "Gerenciamento de Projetos",
    "Programação Back-End",
    "Projeto Integrador: Computação em Nuvem",
    "Empreendedorismo",
    "Projeto Integrador: Desenvolvimento de Aplicativos Móveis",
    "Teste e Qualidade de Software",
]


def _normalizar_nome_materia(nome):
    return unicodedata.normalize("NFC", nome).casefold()


# ==========================================
# CONEXÃO COM O BANCO
# ==========================================

def conectar():
    """Abre uma conexão com o banco SQLite."""
    caminho = caminho_banco_atual()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(caminho, timeout=10)

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

        colunas_materias = {
            coluna["name"]
            for coluna in conexao.execute(
                "PRAGMA table_info(materias)"
            ).fetchall()
        }
        if "semestre" not in colunas_materias:
            conexao.execute("""
                ALTER TABLE materias
                ADD COLUMN semestre INTEGER
                CHECK (semestre IS NULL OR semestre BETWEEN 1 AND 20)
            """)

        # --------------------------------------
        # ASSUNTOS DAS MATÉRIAS
        # --------------------------------------

        # Nova estrutura aditiva: não altera anotações nem registros antigos.
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS assuntos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                materia_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (materia_id)
                    REFERENCES materias (id)
                    ON DELETE CASCADE,
                UNIQUE (materia_id, nome)
            )
        """)

        conexao.execute("""
            CREATE INDEX IF NOT EXISTS idx_assuntos_materia
            ON assuntos (materia_id, nome COLLATE NOCASE)
        """)

        # Anotação pode continuar sem assunto; assim, registros antigos
        # permanecem válidos e um assunto removido apenas desvincula a nota.
        colunas_anotacoes = {
            coluna["name"]
            for coluna in conexao.execute(
                "PRAGMA table_info(anotacoes)"
            ).fetchall()
        }
        if "assunto_id" not in colunas_anotacoes:
            conexao.execute("""
                ALTER TABLE anotacoes
                ADD COLUMN assunto_id INTEGER
                REFERENCES assuntos (id) ON DELETE SET NULL
            """)

        # --------------------------------------
        # METAS SEMANAIS POR MATÉRIA
        # --------------------------------------

        conexao.execute("""
            CREATE TABLE IF NOT EXISTS metas_semanais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                materia_id INTEGER NOT NULL UNIQUE,
                minutos_meta INTEGER NOT NULL,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (materia_id)
                    REFERENCES materias (id)
                    ON DELETE CASCADE
            )
        """)

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
        # MATERIAIS DE ESTUDO POR DISCIPLINA
        # --------------------------------------

        conexao.execute("""
            CREATE TABLE IF NOT EXISTS materiais_estudo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                materia_id INTEGER NOT NULL,
                modulo_id INTEGER,
                titulo TEXT NOT NULL,
                tipo TEXT NOT NULL DEFAULT 'resumo'
                    CHECK (tipo IN ('resumo', 'explicacao', 'exemplo', 'referencia')),
                conteudo TEXT NOT NULL,
                link TEXT NOT NULL DEFAULT '',
                autor TEXT NOT NULL DEFAULT '',
                licenca TEXT NOT NULL DEFAULT '',
                validado INTEGER NOT NULL DEFAULT 0,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (materia_id) REFERENCES materias (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (modulo_id) REFERENCES modulos (id)
                    ON DELETE SET NULL
            )
        """)
        colunas_materiais = {
            coluna["name"]
            for coluna in conexao.execute(
                "PRAGMA table_info(materiais_estudo)"
            ).fetchall()
        }
        if "autor" not in colunas_materiais:
            conexao.execute("""
                ALTER TABLE materiais_estudo
                ADD COLUMN autor TEXT NOT NULL DEFAULT ''
            """)
        if "licenca" not in colunas_materiais:
            conexao.execute("""
                ALTER TABLE materiais_estudo
                ADD COLUMN licenca TEXT NOT NULL DEFAULT ''
            """)
        if "fonte_verificada_em" not in colunas_materiais:
            conexao.execute("ALTER TABLE materiais_estudo ADD COLUMN fonte_verificada_em TEXT")
        if "status_fonte" not in colunas_materiais:
            conexao.execute("ALTER TABLE materiais_estudo ADD COLUMN status_fonte TEXT NOT NULL DEFAULT 'pendente'")
        conexao.execute("""
            CREATE INDEX IF NOT EXISTS idx_materiais_disciplina
            ON materiais_estudo (materia_id, criado_em DESC)
        """)

        # --------------------------------------
        # QUESTÕES E TENTATIVAS
        # --------------------------------------

        conexao.execute("""
            CREATE TABLE IF NOT EXISTS questoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                materia_id INTEGER NOT NULL,
                modulo_id INTEGER,
                enunciado TEXT NOT NULL,
                tipo TEXT NOT NULL CHECK (tipo IN ('multipla_escolha', 'vf', 'numerica')),
                alternativas TEXT NOT NULL DEFAULT '[]',
                resposta_correta TEXT NOT NULL,
                explicacao TEXT NOT NULL DEFAULT '',
                dificuldade TEXT NOT NULL DEFAULT 'media'
                    CHECK (dificuldade IN ('facil', 'media', 'dificil')),
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (materia_id) REFERENCES materias (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (modulo_id) REFERENCES modulos (id)
                    ON DELETE SET NULL
            )
        """)
        conexao.execute("""
            CREATE INDEX IF NOT EXISTS idx_questoes_disciplina
            ON questoes (materia_id, criado_em DESC)
        """)
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS tentativas_questoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                questao_id INTEGER NOT NULL,
                resposta TEXT NOT NULL,
                acertou INTEGER NOT NULL CHECK (acertou IN (0, 1)),
                respondida_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (questao_id) REFERENCES questoes (id)
                    ON DELETE CASCADE
            )
        """)
        conexao.execute("""
            CREATE INDEX IF NOT EXISTS idx_tentativas_questao
            ON tentativas_questoes (questao_id, respondida_em DESC)
        """)

        # --------------------------------------
        # FLASHCARDS E REVISÕES
        # --------------------------------------

        conexao.execute("""
            CREATE TABLE IF NOT EXISTS flashcards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                materia_id INTEGER NOT NULL,
                modulo_id INTEGER,
                frente TEXT NOT NULL,
                verso TEXT NOT NULL,
                proxima_revisao TEXT NOT NULL DEFAULT (date('now', 'localtime')),
                intervalo_dias INTEGER NOT NULL DEFAULT 1,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (materia_id) REFERENCES materias (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (modulo_id) REFERENCES modulos (id)
                    ON DELETE SET NULL
            )
        """)
        conexao.execute("""
            CREATE INDEX IF NOT EXISTS idx_flashcards_revisao
            ON flashcards (materia_id, proxima_revisao)
        """)
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS revisoes_flashcards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flashcard_id INTEGER NOT NULL,
                lembrou INTEGER NOT NULL CHECK (lembrou IN (0, 1)),
                revisada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (flashcard_id) REFERENCES flashcards (id)
                    ON DELETE CASCADE
            )
        """)


        # --------------------------------------
        # MIGRAÇÃO: CONTROLE DE AULAS CONCLUÍDAS
        # --------------------------------------

        colunas_aulas = conexao.execute(
            "PRAGMA table_info(aulas)"
        ).fetchall()

        nomes_colunas = [
            coluna["name"] for coluna in colunas_aulas
        ]

        if "concluida" not in nomes_colunas:
            conexao.execute("""
                ALTER TABLE aulas
                ADD COLUMN concluida INTEGER NOT NULL DEFAULT 0
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

        # --------------------------------------
        # GRADE ADS: SEED IDEMPOTENTE E LIMPEZA ÚNICA
        # --------------------------------------

        conexao.execute("""
            CREATE TABLE IF NOT EXISTS migracoes_aplicadas (
                versao TEXT PRIMARY KEY,
                aplicada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        materias_existentes = conexao.execute("""
            SELECT id, nome
            FROM materias
            ORDER BY id
        """).fetchall()
        por_nome_normalizado = {}
        for materia_existente in materias_existentes:
            chave = _normalizar_nome_materia(materia_existente["nome"])
            por_nome_normalizado.setdefault(chave, []).append(materia_existente)

        ids_grade = []
        for nome in MATERIAS_INICIAIS:
            candidatas = por_nome_normalizado.get(
                _normalizar_nome_materia(nome), []
            )
            exata = next(
                (item for item in candidatas if item["nome"] == nome),
                None
            )
            materia_existente = exata or (candidatas[0] if candidatas else None)

            if materia_existente is None:
                cursor = conexao.execute(
                    "INSERT INTO materias (nome) VALUES (?)",
                    (nome,)
                )
                materia_id = cursor.lastrowid
            else:
                materia_id = materia_existente["id"]
                if materia_existente["nome"] != nome:
                    conexao.execute(
                        "UPDATE materias SET nome = ? WHERE id = ?",
                        (nome, materia_id)
                    )

            ids_grade.append(materia_id)

        migracao_legado = "grade_ads_limpeza_materias_teste_v1"
        migracao_aplicada = conexao.execute(
            "SELECT 1 FROM migracoes_aplicadas WHERE versao = ?",
            (migracao_legado,)
        ).fetchone()

        if migracao_aplicada is None:
            placeholders = ", ".join("?" for _ in ids_grade)
            conexao.execute(
                f"DELETE FROM materias WHERE id NOT IN ({placeholders})",
                ids_grade
            )
            conexao.execute(
                "INSERT INTO migracoes_aplicadas (versao) VALUES (?)",
                (migracao_legado,)
            )


# ==========================================
# EXECUÇÃO DIRETA DO ARQUIVO
# ==========================================

if __name__ == "__main__":
    criar_tabelas()
    print("Banco de dados criado e verificado com sucesso!")
