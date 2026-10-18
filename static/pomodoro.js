
const DURACAO_POMODORO = 25 * 60;

let tempoRestante = DURACAO_POMODORO;
let intervalo = null;
let emExecucao = false;
let concluido = false;

function atualizarVisor() {
    const minutos = Math.floor(tempoRestante / 60);
    const segundos = tempoRestante % 60;

    const visor = document.getElementById("visor-pomodoro");

    visor.textContent =
        String(minutos).padStart(2, "0") +
        ":" +
        String(segundos).padStart(2, "0");
}

function atualizarStatus(mensagem) {
    document.getElementById("status-pomodoro").textContent = mensagem;
}

function iniciarPomodoro() {
    if (emExecucao || concluido) {
        return;
    }

    if (tempoRestante <= 0) {
        return;
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

function pausarPomodoro() {
    if (!emExecucao) {
        return;
    }

    clearInterval(intervalo);
    intervalo = null;
    emExecucao = false;

    atualizarStatus("Cronômetro pausado. Continue quando quiser.");
}

function reiniciarPomodoro() {
    clearInterval(intervalo);
    intervalo = null;

    emExecucao = false;
    concluido = false;
    tempoRestante = DURACAO_POMODORO;

    atualizarVisor();
    atualizarStatus("Cronômetro reiniciado. Pronto para começar?");
}

function concluirPomodoro() {
    clearInterval(intervalo);
    intervalo = null;

    emExecucao = false;
    concluido = true;
    tempoRestante = 0;

    atualizarVisor();
    atualizarStatus("Sessão concluída! Salvando seu estudo...");

    // Envia a matéria e os 25 minutos para o Flask.
    document.getElementById("form-pomodoro").requestSubmit();
}

document.addEventListener("DOMContentLoaded", atualizarVisor);
