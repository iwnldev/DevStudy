
const DURACAO_POMODORO = 25 * 60;

let tempoRestante = DURACAO_POMODORO;
let intervalo = null;
let emExecucao = false;
let concluido = false;
let identificadorSessao = null;
let enviandoFormulario = false;

// Atualiza o número exibido no cronômetro.
function atualizarVisor() {
    const minutos = Math.floor(tempoRestante / 60);
    const segundos = tempoRestante % 60;

    const visor = document.getElementById("visor-pomodoro");

    if (!visor) return;

    visor.textContent =
        String(minutos).padStart(2, "0") + ":" +
        String(segundos).padStart(2, "0");
}

// Atualiza a mensagem de status.
function atualizarStatus(mensagem) {
    const status = document.getElementById("status-pomodoro");

    if (status) {
        status.textContent = mensagem;
    }
}

// Habilita ou desabilita os botões do formulário.
function bloquearBotoesFormulario(bloquear) {
    const formulario = document.getElementById("form-pomodoro");

    if (!formulario) return;

    const botoes = formulario.querySelectorAll("button");

    botoes.forEach((botao) => {
        botao.disabled = bloquear;
    });
}

// Inicia o cronômetro.
function iniciarPomodoro() {
    if (emExecucao || concluido || enviandoFormulario) return;
    if (tempoRestante <= 0) return;

    if (!identificadorSessao) {
        identificadorSessao = crypto.randomUUID();
    }

    emExecucao = true;

    atualizarStatus("Sessão de foco em andamento...");

    intervalo = setInterval(() => {
        tempoRestante--;

        atualizarVisor();

        if (tempoRestante <= 0) {
            concluirPomodoro();
        }
    }, 1000);
}

// Pausa o cronômetro.
function pausarPomodoro() {
    if (!emExecucao) return;

    clearInterval(intervalo);

    intervalo = null;
    emExecucao = false;

    atualizarStatus("Cronômetro pausado. Continue quando quiser.");
}

// Reinicia o cronômetro.
function reiniciarPomodoro() {
    if (enviandoFormulario) return;

    clearInterval(intervalo);

    intervalo = null;
    emExecucao = false;
    concluido = false;
    tempoRestante = DURACAO_POMODORO;
    identificadorSessao = crypto.randomUUID();

    bloquearBotoesFormulario(false);

    atualizarVisor();
    atualizarStatus("Cronômetro reiniciado. Pronto para começar?");
}

// Registra a sessão quando o tempo termina.
function concluirPomodoro() {
    if (concluido || enviandoFormulario) return;

    clearInterval(intervalo);

    intervalo = null;
    emExecucao = false;
    concluido = true;
    tempoRestante = 0;

    atualizarVisor();

    const formulario = document.getElementById("form-pomodoro");

    if (!formulario) {
        atualizarStatus("Não foi possível localizar o formulário.");
        return;
    }

    const campoDuracao = formulario.querySelector(
        '[name="duracao_minutos"]'
    );

    const campoIdentificador = document.getElementById(
        "identificador-sessao"
    );

    if (!campoDuracao || !campoIdentificador) {
        atualizarStatus("Não foi possível preparar o registro.");
        return;
    }

    if (!identificadorSessao) {
        identificadorSessao = crypto.randomUUID();
    }

    // Converte segundos para minutos arredondando para cima.
    campoDuracao.value = Math.ceil(
        (DURACAO_POMODORO - tempoRestante) / 60
    );

    // A sessão completa deve registrar os 25 minutos.
    campoDuracao.value = Math.ceil(DURACAO_POMODORO / 60);

    campoIdentificador.value = identificadorSessao;

    enviandoFormulario = true;

    bloquearBotoesFormulario(true);

    atualizarStatus("Sessão concluída! Salvando seu estudo...");

    formulario.requestSubmit();
}

// Prepara o visor quando a página é carregada.
document.addEventListener("DOMContentLoaded", () => {
    atualizarVisor();
    atualizarStatus("Pronto para começar?");
});
