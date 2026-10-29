(() => {
    "use strict";

    const CHAVE = "devstudy.pomodoro.v1";
    const $ = (seletor) => document.querySelector(seletor);
    const ler = () => {
        try { return JSON.parse(localStorage.getItem(CHAVE) || "null"); }
        catch (_) { return null; }
    };
    const salvar = (estado) => localStorage.setItem(CHAVE, JSON.stringify(estado));
    let estado = ler();
    let intervalo = null;
    const visor = $("#visor-pomodoro");
    const status = $("#status-pomodoro");
    const materia = $("#materia-pomodoro");
    const duracao = $("#duracao-pomodoro");
    const foco = $(".foco-painel");
    const widget = $("#pomodoro-flutuante");

    function restante() {
        if (!estado) return Number(duracao && duracao.value || 25) * 60;
        if (estado.status === "running") {
            return Math.max(0, Math.ceil((estado.terminaEm - Date.now()) / 1000));
        }
        return Math.max(0, estado.restanteSegundos);
    }

    function formatar(segundos) {
        const min = Math.floor(segundos / 60);
        const seg = segundos % 60;
        return `${String(min).padStart(2, "0")}:${String(seg).padStart(2, "0")}`;
    }

    function atualizar() {
        const segundos = restante();
        if (visor) visor.textContent = formatar(segundos);
        const anel = $("#pomodoro-anel");
        if (anel) {
            const total = estado && estado.minutos ? estado.minutos * 60 : Number(duracao && duracao.value || 25) * 60;
            anel.style.setProperty("--angulo", `${Math.max(0, Math.min(360, segundos / total * 360))}deg`);
        }
        const miniVisor = $("#pomodoro-flutuante-tempo");
        if (miniVisor) miniVisor.textContent = formatar(segundos);
        if (widget) {
            const visivel = Boolean(estado && ["running", "paused"].includes(estado.status));
            widget.hidden = !visivel;
            const textoMateria = $("#pomodoro-flutuante-materia");
            if (textoMateria && visivel) {
                textoMateria.textContent = `${estado.materia} · ${estado.status === "paused" ? "pausado" : "sessão ativa"}`;
            }
            const controle = $("#pomodoro-flutuante-controle");
            if (controle) {
                controle.textContent = estado && estado.status === "running" ? "Ⅱ" : "▶";
                controle.setAttribute("aria-label", estado && estado.status === "running" ? "Pausar sessão" : "Continuar sessão");
            }
        }
        if (status && estado) {
            status.textContent = estado.status === "running" ? "FOCO EM ANDAMENTO" : estado.status === "paused" ? "SESSÃO PAUSADA" : "PRONTO PARA COMEÇAR";
        }
        if (estado && estado.status === "running" && segundos <= 0) concluir();
    }

    function iniciar() {
        if (estado && estado.status === "running") return;
        if (materia && !materia.value) {
            materia.focus();
            materia.reportValidity();
            return;
        }
        const minutos = Number(duracao && duracao.value || (estado && estado.minutos) || 25);
        const nomeMateria = (materia && materia.value) || (estado && estado.materia);
        if (!nomeMateria) return;
        const segundos = estado && estado.status === "paused" ? restante() : minutos * 60;
        estado = {
            materia: nomeMateria,
            minutos,
            restanteSegundos: segundos,
            terminaEm: Date.now() + segundos * 1000,
            status: "running",
            identificador: (estado && estado.identificador) || crypto.randomUUID(),
        };
        salvar(estado);
        atualizar();
    }

    function pausar() {
        if (!estado || estado.status !== "running") return;
        estado.restanteSegundos = restante();
        estado.status = "paused";
        estado.terminaEm = null;
        salvar(estado);
        atualizar();
    }

    function reiniciar() {
        localStorage.removeItem(CHAVE);
        estado = null;
        if (status) status.textContent = "PRONTO PARA COMEÇAR";
        atualizar();
    }

    async function concluir() {
        if (!estado || estado.status !== "running" || estado.salvando) return;
        estado.status = "saving";
        estado.salvando = true;
        salvar(estado);
        atualizar();
        const formulario = $("#pomodoro-salvar-form") || $("#form-pomodoro");
        if (!formulario) return;
        const campoMateria = formulario.querySelector('[name="materia"]');
        const campoId = formulario.querySelector('[name="identificador"]');
        const campoDuracao = formulario.querySelector('[name="duracao_minutos"]');
        const token = formulario.querySelector('[name="csrf_token"]');
        const dados = new FormData();
        dados.set("csrf_token", token ? token.value : "");
        dados.set("identificador", estado.identificador);
        dados.set("materia", estado.materia);
        dados.set("duracao_minutos", String(estado.minutos));
        if (campoMateria) campoMateria.value = estado.materia;
        if (campoId) campoId.value = estado.identificador;
        if (campoDuracao) campoDuracao.value = String(estado.minutos);
        try {
            const resposta = await fetch(formulario.action, { method: "POST", body: dados, credentials: "same-origin" });
            if (!resposta.ok) throw new Error("Falha ao registrar a sessão");
            localStorage.removeItem(CHAVE);
            estado = null;
            if (status) status.textContent = "SESSÃO CONCLUÍDA · TEMPO SALVO";
            if (widget) widget.hidden = true;
            if (visor) visor.textContent = "00:00";
        } catch (_) {
            estado.status = "paused";
            estado.restanteSegundos = 0;
            estado.terminaEm = null;
            estado.salvando = false;
            salvar(estado);
            if (status) status.textContent = "FOCO CONCLUÍDO · TOQUE EM CONTINUAR PARA SALVAR";
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        if (estado && estado.status === "saving") estado.status = "running";
        if (materia && estado && estado.materia) materia.value = estado.materia;
        if (duracao && estado && estado.minutos) duracao.value = String(estado.minutos);

        document.querySelectorAll(".pomodoro-opcao").forEach((botao) => {
            if (duracao && Number(botao.dataset.minutos) === Number(duracao.value)) botao.classList.add("ativa");
            botao.addEventListener("click", () => {
                if (estado && ["running", "paused"].includes(estado.status)) return;
                document.querySelectorAll(".pomodoro-opcao").forEach((item) => item.classList.remove("ativa"));
                botao.classList.add("ativa");
                if (duracao) duracao.value = botao.dataset.minutos;
                atualizar();
            });
        });

        $("#botao-iniciar-pomodoro")?.addEventListener("click", iniciar);
        $("#botao-pausar-pomodoro")?.addEventListener("click", pausar);
        $("#botao-reiniciar-pomodoro")?.addEventListener("click", reiniciar);
        $("#pomodoro-flutuante-controle")?.addEventListener("click", () => {
            if (estado && estado.status === "running") pausar(); else iniciar();
        });
        materia?.addEventListener("change", () => {
            if (!estado || !["running", "paused"].includes(estado.status)) atualizar();
        });

        atualizar();
        intervalo = window.setInterval(atualizar, 500);
        window.addEventListener("storage", (evento) => {
            if (evento.key === CHAVE) { estado = ler(); atualizar(); }
        });
    });
})();
