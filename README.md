# DevStudy 📚

O **DevStudy** é uma aplicação web desenvolvida em Python com Flask para auxiliar na organização dos estudos. O projeto reúne ferramentas para registrar conteúdos estudados, acompanhar metas e manter uma rotina de aprendizado.

## ✨ Funcionalidades

- 📝 Cadastro, edição e exclusão de anotações.
- 🔗 Associação opcional de anotações a assuntos da matéria.
- 🔎 Busca por conteúdo e categoria, filtros e ordenação da biblioteca.
- ⭐ Favoritos para destacar anotações importantes.
- 📚 Matérias organizadas por assuntos, além de cursos em módulos e aulas.
- 🎓 Grade curricular de ADS com 23 disciplinas oficiais, filtros por semestre e acompanhamento individual do progresso.
- 🧭 Semestre configurável em cada disciplina; conteúdos podem ser organizados em cursos, módulos e aulas.
- 📖 Materiais por disciplina com autoria, fonte, licença e marcação de validação.
- 🧠 Exercícios de múltipla escolha, verdadeiro/falso e resposta numérica, com correção no servidor e histórico de tentativas.
- 🗂️ Flashcards com revisões espaçadas e recomendações baseadas nos dados reais de estudo.
- ✨ Tutor opcional por IA integrado à API de Responses da OpenAI.
- 🔐 Cadastro, login e bancos de estudo separados por usuário.
- ✉️ Confirmação de e-mail e recuperação de senha com links assinados e temporários.
- 📚 Pacote inicial autoral com resumo, exercício e flashcards para cada uma das 23 disciplinas, ligado a fontes públicas oficiais.
- 🪜 Trilhas de aprendizagem em três etapas com atividades iniciais por disciplina.
- 📈 Indicadores de minutos estudados na semana, materiais, exercícios e revisões por disciplina.
- 🧾 Curadoria de fontes com autoria, termos/licença, status e data de conferência registrada.
- 🎥 Videoaulas públicas por módulo, com recomendações diretas e sugestões da comunidade sujeitas à revisão.
- 🎯 Metas diárias e metas semanais por matéria.
- ⏱️ Registro de sessões de estudo.
- 📊 Dashboard semanal, comparação entre semanas, histórico e calendário.
- 🍅 Temporizador Pomodoro para auxiliar na concentração.
- 📤 Exportação de anotações e sessões em CSV.
- 🗄️ Armazenamento de dados em banco de dados SQLite.
- 🧪 Testes automatizados com pytest.

## 🛠️ Tecnologias utilizadas

- Python
- Flask
- SQLite
- HTML e CSS
- pytest
- Git e GitHub

## 🚀 Como executar o projeto

### 1. Clone o repositório

```bash
git clone https://github.com/iwnldev/DevStudy
```

Entre na pasta do projeto:

```bash
cd DevStudy
```

### 2. Crie um ambiente virtual

```bash
python -m venv .venv
```

Ative o ambiente virtual no Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Instale as dependências

```bash
python -m pip install -r requirements.txt
```

### 4. Configure a chave secreta

O aplicativo exige a variável de ambiente `DEVSTUDY_SECRET_KEY`. Defina uma chave local no PowerShell antes de executar:

```powershell
$env:DEVSTUDY_SECRET_KEY = "sua-chave-local"
```

Use uma chave secreta própria e não a publique no GitHub.

### 5. Configure o tutor de IA (opcional)

Para ativar o tutor, configure uma chave de API da OpenAI no ambiente. A chave não deve ser colocada no código nem compartilhada:

```powershell
$env:OPENAI_API_KEY = "sua-chave-de-api"
$env:OPENAI_MODEL = "gpt-6-luna"
```

As perguntas são enviadas à API quando o tutor é usado. O uso da API pode gerar cobrança conforme a conta e o modelo configurado.

### 6. Execute a aplicação

```bash
python app.py
```

Abra no navegador o endereço local indicado pelo Flask no terminal.

### Compartilhar com colegas

O aplicativo oferece as páginas `/registrar` e `/login`. Cada conta recebe um banco SQLite próprio em `instance/usuarios/`; as credenciais ficam em `instance/contas.db` e as senhas são armazenadas com hash. Novas contas recebem a grade e o pacote inicial de conteúdo. Anotações, tentativas, progresso e materiais adicionados por cada pessoa permanecem separados.

Para colegas acessarem pela internet, publique o Flask em um servidor com HTTPS, defina uma `DEVSTUDY_SECRET_KEY` persistente e forte, mantenha `instance/` em armazenamento persistente e use um servidor WSGI de produção. O servidor local de desenvolvimento não publica o app. A chave da API do tutor, se configurada, é compartilhada pelo servidor e cada usuário tem limite de 10 perguntas por dia; o uso da API pode gerar cobrança.

Para moderar sugestões de videoaulas, configure `DEVSTUDY_MODERADORES` com um ou mais e-mails de contas já cadastradas, separados por vírgulas. Essas contas verão o link “Revisar sugestões da comunidade” nos módulos e poderão aprovar ou rejeitar links antes da publicação para todos.

No Windows PowerShell, por exemplo:

```powershell
$env:DEVSTUDY_MODERADORES = "seu-email@exemplo.com"
```

O repositório inclui `render.yaml` como configuração de referência para Render, com Gunicorn, verificação de saúde e disco persistente montado em `/var/data`. A configuração de disco do Render exige um serviço pago e fica limitada a uma instância; revise o plano e o custo na sua conta antes de criar o serviço. A Blueprint não foi publicada nem conectada a uma conta.

#### E-mail transacional

Confirmação e recuperação exigem SMTP. Configure `DEVSTUDY_MAIL_SERVER`, `DEVSTUDY_MAIL_PORT`, `DEVSTUDY_MAIL_USERNAME`, `DEVSTUDY_MAIL_PASSWORD` e `DEVSTUDY_MAIL_FROM` como variáveis secretas/privadas no provedor. Use TLS na porta 587; para SSL direto na porta 465, defina `DEVSTUDY_MAIL_USE_SSL=1`. Configure `DEVSTUDY_PUBLIC_URL` com a URL HTTPS pública para links seguros nos e-mails. Em desenvolvimento, `FLASK_DEBUG=1` registra os links no terminal quando SMTP não está configurado.

As contas precisam confirmar o e-mail antes do primeiro acesso. Links de confirmação expiram em 24 horas; links de recuperação expiram em 30 minutos e são invalidados após a redefinição.

Os resumos iniciais são textos autorais de introdução, não uma reprodução das páginas citadas. Cada disciplina inclui exercício, flashcards e uma trilha inicial em três etapas. Esses roteiros são sugestões, não substituem a ementa da faculdade. A conferência de uma fonte é uma declaração manual do usuário; o sistema registra a data, mas não verifica automaticamente conteúdo, licença ou disponibilidade do link.

## 🧪 Executando os testes

Com o ambiente virtual ativado, execute na pasta raiz do projeto:

```powershell
$env:PYTHONPATH = (Get-Location).Path
pytest -v
```

O comando executa os testes automatizados do projeto.

## 🎯 Objetivo do projeto

O DevStudy é um projeto de aprendizado e portfólio, desenvolvido para praticar programação em Python, desenvolvimento web, persistência de dados, validações e testes automatizados.

## 👨‍💻 Autor

Desenvolvido como projeto de estudo em Análise e Desenvolvimento de Sistemas.
