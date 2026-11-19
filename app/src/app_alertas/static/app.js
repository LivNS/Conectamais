/* Conecta+: letra maior, tipo de celular, ouvir, quizzes, treinos seguros e progresso local.
   Nada aqui envia texto de mensagem ao servidor; só contagens anônimas (ver /privacidade). */
(function () {
  "use strict";

  var CHAVE_APARELHO = "mvp.aparelho";
  var CHAVE_PROGRESSO = "mvp.progresso";
  var LETRAS = "ABCDEF";
  var html = document.documentElement;

  function guardar(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* modo privado */ } }
  function ler(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function apagar(k) { try { localStorage.removeItem(k); } catch (e) {} }
  function el(tag, classe, texto) {
    var e = document.createElement(tag);
    if (classe) e.className = classe;
    if (texto != null) e.textContent = texto;
    return e;
  }
  function $(sel, raiz) { return (raiz || document).querySelector(sel); }
  function $$(sel, raiz) { return Array.prototype.slice.call((raiz || document).querySelectorAll(sel)); }
  function mostrar(no, sim) { if (no) no.hidden = !sim; }

  function novoId() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      var r = Math.random() * 16 | 0; return (c === "x" ? r : (r & 3 | 8)).toString(16);
    });
  }
  function aparelho() {
    var id = ler(CHAVE_APARELHO);
    if (!id) { id = novoId(); guardar(CHAVE_APARELHO, id); }
    return id;
  }
  function progresso() { try { return JSON.parse(ler(CHAVE_PROGRESSO)) || {}; } catch (e) { return {}; } }
  function marcar(etapa, dados) { var p = progresso(); p[etapa] = dados || true; guardar(CHAVE_PROGRESSO, JSON.stringify(p)); }

  function enviar(evento) {
    evento.aparelho = aparelho();
    try {
      fetch("/api/eventos", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(evento), keepalive: true }).catch(function () {});
    } catch (e) { /* sem rede: o progresso local continua */ }
  }
  $$('input[name="aparelho"]').forEach(function (i) { i.value = aparelho(); });

  function concluirPratica(id) {
    if (!progresso()["c:" + id]) enviar({ tipo: "pratica_fim", licao: id });
    marcar("c:" + id);
  }

  // ---------- tamanho da letra ----------
  $$("[data-letra]").forEach(function (b) {
    b.addEventListener("click", function () {
      var atual = Number(html.getAttribute("data-letra") || "1");
      var prox = atual >= 3 ? 1 : atual + 1;
      if (prox === 1) html.removeAttribute("data-letra"); else html.setAttribute("data-letra", String(prox));
      guardar("c.letra", prox === 1 ? "" : String(prox));
      b.setAttribute("aria-label", "Tamanho da letra: " + ["normal", "grande", "maior ainda"][prox - 1] + ". Toque para mudar.");
    });
  });

  // ---------- tipo de celular ----------
  var NOMES = { android: "Android", iphone: "iPhone" };
  function pintarCelular() {
    var c = html.getAttribute("data-celular") || "android";
    $$("[data-nome-celular]").forEach(function (s) { s.textContent = NOMES[c]; });
    $$("[data-escolher-celular]").forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-escolher-celular") === c ? "true" : "false");
    });
    document.dispatchEvent(new CustomEvent("celular-mudou"));
  }
  $$("[data-escolher-celular]").forEach(function (b) {
    b.addEventListener("click", function () {
      var c = b.getAttribute("data-escolher-celular");
      html.setAttribute("data-celular", c);
      guardar("c.celular", c);
      pintarCelular();
      var caixa = $("[data-caixa-celular]");
      if (caixa) caixa.hidden = true;
    });
  });
  $$("[data-trocar-celular]").forEach(function (b) {
    b.addEventListener("click", function () { var caixa = $("[data-caixa-celular]"); if (caixa) caixa.hidden = !caixa.hidden; });
  });
  pintarCelular();

  // ---------- ouvir ----------
  $$("[data-ouvir]").forEach(function (b) {
    if (!("speechSynthesis" in window)) { b.hidden = true; return; }
    b.addEventListener("click", function () {
      if (speechSynthesis.speaking) { speechSynthesis.cancel(); b.removeAttribute("aria-pressed"); return; }
      var alvo = $(b.getAttribute("data-ouvir"));
      if (!alvo) return;
      var fala = new SpeechSynthesisUtterance(alvo.innerText);
      fala.lang = "pt-BR"; fala.rate = 0.88;
      fala.onend = function () { b.removeAttribute("aria-pressed"); };
      b.setAttribute("aria-pressed", "true");
      speechSynthesis.speak(fala);
    });
  });

  // ---------- quiz (lições de segurança, testes e aulas) ----------
  function montarQuiz(caixa) {
    var dadosEl = caixa.parentNode.querySelector("[data-quiz-dados]");
    if (!dadosEl) return;
    var perguntas = JSON.parse(dadosEl.textContent);
    var tipo = caixa.getAttribute("data-tipo");
    var licao = caixa.getAttribute("data-licao");
    var i = 0, acertos = 0, resultados = [];

    function mostrarPergunta() {
      var q = perguntas[i];
      caixa.innerHTML = "";
      if (perguntas.length > 1) {
        caixa.appendChild(el("p", "passo", "Pergunta " + (i + 1) + " de " + perguntas.length));
        var barra = el("div", "barra"); barra.setAttribute("aria-hidden", "true");
        var pre = el("i"); pre.style.width = (100 * i / perguntas.length) + "%"; barra.appendChild(pre);
        caixa.appendChild(barra);
      }
      var titulo = el("h2", "pergunta", q.pergunta); titulo.tabIndex = -1;
      var lista = el("div", "opcoes"); lista.setAttribute("role", "group"); lista.setAttribute("aria-label", "Respostas");
      var retorno = el("div", "retorno"); retorno.setAttribute("role", "status");
      q.opcoes.forEach(function (texto, k) {
        var b = el("button", "opcao"); b.type = "button";
        var l = el("span", "letra", LETRAS[k]); l.setAttribute("aria-hidden", "true");
        b.appendChild(l); b.appendChild(el("span", null, texto));
        b.addEventListener("click", function () { responder(k, lista, retorno, q); });
        lista.appendChild(b);
      });
      caixa.appendChild(titulo); caixa.appendChild(lista); caixa.appendChild(retorno);
      if (i > 0) titulo.focus();
    }
    function responder(k, lista, retorno, q) {
      var certo = k === q.correta;
      if (certo) acertos++;
      resultados.push(certo);
      $$("button", lista).forEach(function (b, j) {
        b.disabled = true;
        if (j === q.correta) b.classList.add("certa"); else if (j === k) b.classList.add("errada");
      });
      var p = el("p");
      p.appendChild(el("strong", null, certo ? "Isso mesmo. " : "Não é bem assim. "));
      p.appendChild(document.createTextNode(q.explicacao));
      retorno.className = "retorno " + (certo ? "ok" : "nao");
      retorno.appendChild(p);
      var seguir = el("button", "botao", i + 1 < perguntas.length ? "Próxima pergunta" : "Ver meu resultado");
      seguir.type = "button";
      seguir.addEventListener("click", function () { i++; if (i < perguntas.length) mostrarPergunta(); else concluir(); });
      retorno.appendChild(seguir);
      seguir.focus();
    }
    function concluir() {
      var total = perguntas.length;
      caixa.innerHTML = "";
      var fim = el("p", "placar", "Você acertou " + acertos + " de " + total + ".");
      fim.tabIndex = -1;
      var pontos = el("div", "placar-pontos"); pontos.setAttribute("aria-hidden", "true");
      resultados.forEach(function (ok) { pontos.appendChild(el("i", ok ? "ok" : "")); });
      caixa.appendChild(fim); caixa.appendChild(pontos);
      fim.focus();
      if (tipo === "licao") {
        enviar({ tipo: "quiz_licao", licao: licao, acertos: acertos, total: total });
        enviar({ tipo: "licao_fim", licao: licao });
        marcar(licao, { acertos: acertos, total: total });
      } else {
        enviar({ tipo: tipo === "pre" ? "pre_teste" : "pos_teste", acertos: acertos, total: total });
        var pre = progresso().pre;
        marcar(tipo, { acertos: acertos, total: total });
        var comp = $("[data-comparacao]");
        if (comp && tipo === "pos" && pre && pre.total) {
          comp.textContent = "No começo você acertou " + pre.acertos + " de " + pre.total + ". Agora acertou " + acertos + " de " + total + ".";
          comp.hidden = false;
        } else if (comp && tipo === "pre") {
          comp.textContent = "Pronto. Agora vamos às aulas.";
          comp.hidden = false;
        }
      }
      mostrar($("[data-depois-quiz]"), true);
    }
    mostrarPergunta();
  }
  $$("[data-quiz]").forEach(montarQuiz);
  var artigo = $("#licao[data-licao]");
  if (artigo) enviar({ tipo: "licao_inicio", licao: artigo.getAttribute("data-licao") });

  // ---------- progresso nas listas ----------
  function pintarProgresso() {
    var p = progresso();
    function feito(id) { return !!(p[id] || p["c:" + id]); }
    $$("[data-progresso]").forEach(function (n) {
      n.classList.toggle("feito", feito(n.getAttribute("data-progresso")));
      n.classList.remove("atual");
    });
    ["[data-nivel='1']", "[data-nivel='2']"].forEach(function (sel) {
      var grupo = $(sel);
      if (!grupo) return;
      var itens = $$("[data-progresso]", grupo);
      var prox = itens.filter(function (n) { return !n.classList.contains("feito"); })[0];
      if (prox) prox.classList.add("atual");
      var cont = $("[data-contagem]", grupo.parentNode);
      var feitos = itens.filter(function (n) { return n.classList.contains("feito"); }).length;
      if (cont) cont.textContent = feitos + " de " + itens.length + " feitas";
    });
    var nivel1 = $("[data-nivel='1']");
    var cont = $("[data-continuar]");
    if (cont && nivel1) {
      var proximo = $$("[data-progresso]", nivel1).filter(function (n) { return !n.classList.contains("feito"); })[0];
      if (proximo) {
        cont.href = proximo.getAttribute("href");
        $("[data-continuar-nome]", cont).textContent = $("b", proximo).textContent;
        $("[data-continuar-rotulo]", cont).textContent = Object.keys(p).length ? "Continuar" : "Comece por aqui";
      } else {
        $("[data-continuar-rotulo]", cont).textContent = "Você terminou o Nível 1!";
        $("[data-continuar-nome]", cont).textContent = "Vamos ao Nível 2";
        cont.href = "#nivel2";
      }
    }
    var chip = $("[data-progresso-inicio]");
    if (chip) {
      var ids = (chip.getAttribute("data-progresso-inicio") || "").split(",");
      var n = ids.filter(feito).length;
      chip.textContent = n ? n + " de " + ids.length + " lições feitas" : "Comece aqui";
    }
  }
  pintarProgresso();

  // ---------- apagar dados ----------
  $$("[data-apagar]").forEach(function (b) {
    b.addEventListener("click", function () {
      var id = ler(CHAVE_APARELHO);
      var msg = $("[data-apagar-msg]");
      function pronto() {
        apagar(CHAVE_PROGRESSO); apagar(CHAVE_APARELHO);
        if (msg) msg.textContent = "Seus dados foram apagados.";
        pintarProgresso();
      }
      if (!id) return pronto();
      fetch("/api/eventos/" + encodeURIComponent(id), { method: "DELETE" }).then(pronto)
        .catch(function () { if (msg) msg.textContent = "Não deu para apagar agora. Tente de novo com internet."; });
    });
  });

  // ---------- segurar (para treinos): funciona com dedo, mouse e teclado ----------
  function aoSegurar(no, ms, fn, curto) {
    var timer = null, inicio = 0, disparou = false;
    function comecar(e) {
      if (e && e.button > 0) return;
      disparou = false; inicio = Date.now();
      timer = setTimeout(function () { disparou = true; fn(); }, ms);
    }
    function parar() {
      if (!timer) return;
      clearTimeout(timer); timer = null;
      if (!disparou && curto && Date.now() - inicio < ms) curto();
    }
    no.addEventListener("pointerdown", comecar);
    no.addEventListener("pointerup", parar);
    no.addEventListener("pointercancel", parar);
    no.addEventListener("contextmenu", function (e) { e.preventDefault(); });
    no.addEventListener("keydown", function (e) { if ((e.key === "Enter" || e.key === " ") && !e.repeat) { e.preventDefault(); fn(); } });
  }

  // ---------- lição: mandar áudio ----------
  var audio = $("[data-licao-audio]");
  if (audio) (function () {
    var fase = 0, gravando = false, inicio = 0;
    var titulos = JSON.parse(audio.getAttribute("data-titulos"));
    var erro = $("[data-erro]", audio);
    function pintar() {
      $$("[data-fase]", audio).forEach(function (n) {
        var fases = n.getAttribute("data-fase").split(",");
        n.hidden = fases.indexOf(String(fase)) < 0;
      });
      $("[data-titulo]", audio).textContent = titulos[fase];
      $("[data-num]", audio).textContent = String(fase + 1);
      $$("[data-bolinha]", audio).forEach(function (b, i) { b.classList.toggle("on", i <= fase); });
      var mic = $("[data-mic]", audio);
      mic.classList.toggle("alvo-mic", fase === 1 && !gravando);
      mic.classList.toggle("anel", fase === 1 && !gravando);
      mic.classList.toggle("gravando-agora", gravando);
      mostrar($("[data-gravando]", audio), gravando);
      mostrar($("[data-mao-mic]", audio), fase === 1 && !gravando);
      if (fase === 2) concluirPratica("audio");
    }
    function avisar(t) { erro.textContent = t; erro.hidden = !t; }
    $$("[data-conversa]", audio).forEach(function (b) {
      b.addEventListener("click", function () {
        if (b.hasAttribute("data-alvo")) { fase = 1; avisar(""); pintar(); }
        else avisar("Essa não. Toque na Maria, a que está em amarelo.");
      });
    });
    var mic = $("[data-mic]", audio);
    function comecar() { if (fase !== 1) return; gravando = true; inicio = Date.now(); avisar(""); pintar(); }
    function terminar() {
      if (!gravando) return;
      gravando = false;
      if (Date.now() - inicio < 500) { avisar("Segure um pouco mais enquanto fala."); }
      else { fase = 2; avisar(""); }
      pintar();
    }
    mic.addEventListener("pointerdown", function (e) { e.preventDefault(); comecar(); });
    mic.addEventListener("pointerup", terminar);
    mic.addEventListener("pointercancel", terminar);
    mic.addEventListener("contextmenu", function (e) { e.preventDefault(); });
    mic.addEventListener("keydown", function (e) { if ((e.key === " " || e.key === "Enter") && !e.repeat) { e.preventDefault(); comecar(); } });
    mic.addEventListener("keyup", function (e) { if (e.key === " " || e.key === "Enter") { e.preventDefault(); terminar(); } });
    $$("[data-reiniciar]", audio).forEach(function (b) { b.addEventListener("click", function () { fase = 0; avisar(""); pintar(); }); });
    $$("[data-voltar-passo]", audio).forEach(function (b) { b.addEventListener("click", function () { fase = Math.max(0, fase - 1); avisar(""); pintar(); }); });
    pintar();
  })();

  // ---------- lição: copiar e colar ----------
  var copiar = $("[data-licao-copiar]");
  if (copiar) (function () {
    var fase = 0;
    var titulos = JSON.parse(copiar.getAttribute("data-titulos"));
    var erro = $("[data-erro]", copiar);
    var texto = $("[data-texto]", copiar);
    var caixa = $("[data-caixa]", copiar);
    function avisar(t) { erro.textContent = t; erro.hidden = !t; }
    function pintar() {
      $$("[data-fase]", copiar).forEach(function (n) {
        n.hidden = n.getAttribute("data-fase").split(",").indexOf(String(fase)) < 0;
      });
      $("[data-titulo]", copiar).textContent = titulos[Math.min(fase, titulos.length - 1)];
      $("[data-num]", copiar).textContent = String(Math.min(fase + 1, 5));
      $$("[data-bolinha]", copiar).forEach(function (b, i) { b.classList.toggle("on", i <= fase); });
      texto.classList.toggle("alvo", fase === 0); texto.classList.toggle("anel", fase === 0);
      texto.classList.toggle("selecionado", fase === 1 || fase === 2);
      caixa.classList.toggle("alvo", fase === 2); caixa.classList.toggle("anel", fase === 2);
      if (fase >= 4) { caixa.textContent = texto.textContent; caixa.classList.add("preenchida"); concluirPratica("copiar"); }
      else { caixa.textContent = "Caixa de mensagem"; caixa.classList.remove("preenchida"); }
    }
    aoSegurar(texto, 600, function () { if (fase === 0) { fase = 1; avisar(""); pintar(); } },
      function () { if (fase === 0) avisar("Encoste o dedo e não solte até aparecer o menu."); });
    $("[data-copiar]", copiar).addEventListener("click", function () { fase = 2; avisar(""); pintar(); });
    aoSegurar(caixa, 600, function () { if (fase === 2) { fase = 3; avisar(""); pintar(); } },
      function () { if (fase === 2) avisar("Segure o dedo na caixa até aparecer Colar."); });
    $("[data-colar]", copiar).addEventListener("click", function () { fase = 4; avisar(""); pintar(); });
    $$("[data-reiniciar]", copiar).forEach(function (b) { b.addEventListener("click", function () { fase = 0; avisar(""); pintar(); }); });
    pintar();
  })();

  // ---------- treino do toque ----------
  var treino = $("[data-treino]");
  if (treino) (function () {
    var aba = "tocar", toques = 0, carga = 0, timer = null, feitos = {};
    var posicoes = [[38, 30], [8, 8], [62, 62]];
    var msg = $("[data-msg]", treino);
    function avisar(t, ok) { msg.textContent = t; msg.hidden = !t; msg.className = ok ? "comparacao" : "erro-gentil"; }
    function concluir(qual, t) { feitos[qual] = true; avisar(t, true); pintar(); if (feitos.tocar && feitos.segurar && feitos.arrastar) concluirPratica("toque"); }
    function pintar() {
      $$("[data-aba]", treino).forEach(function (b) {
        var id = b.getAttribute("data-aba");
        b.setAttribute("aria-selected", id === aba ? "true" : "false");
        b.classList.toggle("feito", !!feitos[id]);
      });
      $$("[data-painel]", treino).forEach(function (p) { p.hidden = p.getAttribute("data-painel") !== aba; });
      var alvo = $("[data-alvo-toque]", treino);
      var pos = posicoes[Math.min(toques, 2)];
      alvo.style.left = pos[0] + "%"; alvo.style.top = pos[1] + "%";
      alvo.hidden = toques >= 3;
      $("[data-contagem-toque]", treino).textContent = Math.min(toques, 3) + " de 3 toques";
      $("[data-carga] i", treino).style.width = (feitos.segurar ? 100 : carga) + "%";
      $("[data-carga] span", treino).textContent = feitos.segurar ? "Feito!" : timer ? "Continue segurando…" : "Segure aqui";
      mostrar($("[data-tudo]", treino), feitos.tocar && feitos.segurar && feitos.arrastar);
    }
    $$("[data-aba]", treino).forEach(function (b) {
      b.addEventListener("click", function () { aba = b.getAttribute("data-aba"); avisar(""); pintar(); });
    });
    $("[data-alvo-toque]", treino).addEventListener("click", function () {
      toques++;
      if (toques >= 3) concluir("tocar", "Muito bem! Tocar é o gesto mais usado no celular.");
      else pintar();
    });
    var botao = $("[data-carga]", treino);
    function inicio(e) {
      if (feitos.segurar) return;
      if (e) e.preventDefault();
      clearInterval(timer); carga = 0; avisar("");
      timer = setInterval(function () {
        carga = Math.min(100, carga + 6);
        if (carga >= 100) { clearInterval(timer); timer = null; concluir("segurar", "Perfeito! É assim que se grava um áudio."); }
        else pintar();
      }, 100);
      pintar();
    }
    function fim() {
      if (!timer) return;
      clearInterval(timer); timer = null;
      if (carga < 100) { carga = 0; avisar("Soltou um pouco cedo. Tente de novo e só tire o dedo quando a barra encher."); }
      pintar();
    }
    botao.addEventListener("pointerdown", inicio);
    botao.addEventListener("pointerup", fim);
    botao.addEventListener("pointercancel", fim);
    botao.addEventListener("contextmenu", function (e) { e.preventDefault(); });
    botao.addEventListener("keydown", function (e) { if ((e.key === " " || e.key === "Enter") && !e.repeat) inicio(e); });
    botao.addEventListener("keyup", function (e) { if (e.key === " " || e.key === "Enter") fim(); });
    var trilho = $("[data-trilho]", treino);
    function arrastar() { if (Number(trilho.value) >= 100 && !feitos.arrastar) concluir("arrastar", "Chegou lá! Arrastar serve para rolar a tela e desbloquear o celular."); }
    trilho.addEventListener("input", arrastar);
    trilho.addEventListener("change", arrastar);
    pintar();
  })();

  // ---------- lição em passos (Android ou iPhone) ----------
  var passos = $("[data-licao-passos]");
  if (passos) (function () {
    var dados = JSON.parse($("[data-passos-dados]", passos).textContent);
    var id = passos.getAttribute("data-licao-passos");
    var i = 0, fim = false;
    function lista() { return dados[html.getAttribute("data-celular") === "iphone" ? "iphone" : "android"]; }
    function pintar() {
      var l = lista();
      if (i >= l.length) i = l.length - 1;
      mostrar($("[data-em-passos]", passos), !fim);
      mostrar($("[data-fim]", passos), fim);
      $("[data-num]", passos).textContent = String(i + 1);
      $("[data-total]", passos).textContent = String(l.length);
      $("[data-passo-texto]", passos).textContent = l[i];
      var bol = $("[data-bolinhas]", passos); bol.innerHTML = "";
      l.forEach(function (_, k) { bol.appendChild(el("i", k <= i ? "on" : "")); });
      mostrar($("[data-anterior]", passos), i > 0);
      $("[data-proximo]", passos).textContent = i + 1 < l.length ? "Já fiz, próximo" : "Pronto, consegui!";
    }
    $("[data-proximo]", passos).addEventListener("click", function () {
      if (i + 1 < lista().length) i++; else { fim = true; concluirPratica(id); }
      pintar();
      var t = $("[data-passo-texto]", passos); if (t && !fim) t.focus();
    });
    $("[data-anterior]", passos).addEventListener("click", function () { i = Math.max(0, i - 1); pintar(); });
    $$("[data-reiniciar]", passos).forEach(function (b) { b.addEventListener("click", function () { i = 0; fim = false; pintar(); }); });
    document.addEventListener("celular-mudou", function () { i = 0; fim = false; pintar(); });
    pintar();
  })();

  // ---------- aula do Nível 2 (telas + uma pergunta) ----------
  var aula = $("[data-aula]");
  if (aula) (function () {
    var id = aula.getAttribute("data-aula");
    var telas = $$("[data-tela]", aula);
    var total = telas.length + 1;
    var i = 0, resposta = null;
    var p = JSON.parse($("[data-pergunta-dados]", aula).textContent);
    function pintar() {
      telas.forEach(function (t, k) { t.hidden = k !== i; });
      mostrar($("[data-pergunta]", aula), i === telas.length);
      mostrar($("[data-fim]", aula), i > telas.length);
      mostrar($("[data-rodape]", aula), i <= telas.length);
      $$("[data-bolinhas] i", aula).forEach(function (b, k) { b.classList.toggle("on", k <= i); });
      mostrar($("[data-anterior]", aula), i > 0 && i <= telas.length);
      var prox = $("[data-proximo]", aula);
      prox.hidden = i === telas.length && resposta === null;
      prox.textContent = i < telas.length - 1 ? "Próximo" : i === telas.length - 1 ? "Responder a pergunta" : "Concluir a aula";
    }
    var opcoes = $("[data-opcoes]", aula);
    p.opcoes.forEach(function (t, k) {
      var b = el("button", "opcao"); b.type = "button";
      var l = el("span", "letra", LETRAS[k]); l.setAttribute("aria-hidden", "true");
      b.appendChild(l); b.appendChild(el("span", null, t));
      b.addEventListener("click", function () {
        resposta = k;
        $$("button", opcoes).forEach(function (o, j) {
          o.classList.remove("certa", "errada");
          if (j === p.correta) o.classList.add("certa"); else if (j === k) o.classList.add("errada");
        });
        var r = $("[data-retorno]", aula);
        r.className = "retorno " + (k === p.correta ? "ok" : "nao");
        r.innerHTML = ""; r.appendChild(el("p", null, k === p.correta ? p.certo : p.errado));
        pintar();
      });
      opcoes.appendChild(b);
    });
    $("[data-proximo]", aula).addEventListener("click", function () {
      i = Math.min(total, i + 1);
      if (i === total) concluirPratica(id);
      pintar(); window.scrollTo(0, 0);
    });
    $("[data-anterior]", aula).addEventListener("click", function () { i = Math.max(0, i - 1); pintar(); });
    $$("[data-reiniciar]", aula).forEach(function (b) {
      b.addEventListener("click", function () {
        i = 0; resposta = null; $$("button", opcoes).forEach(function (o) { o.classList.remove("certa", "errada"); });
        $("[data-retorno]", aula).innerHTML = ""; pintar();
      });
    });
    pintar();
  })();

  // ---------- É golpe?: colar com um toque ----------
  var colar = $("[data-colar-mensagem]");
  if (colar) (function () {
    var campo = $("#texto");
    var aviso = $("[data-colar-aviso]");
    var confirma = $("[data-confirma]");
    function atualizar() { mostrar(confirma, campo.value.trim().length > 0); }
    campo.addEventListener("input", atualizar);
    colar.addEventListener("click", function () {
      function falhou() {
        aviso.textContent = "Não deu para colar sozinho. Toque e segure dentro da caixa abaixo e escolha Colar.";
        aviso.hidden = false; campo.focus();
      }
      if (!navigator.clipboard || !navigator.clipboard.readText) return falhou();
      navigator.clipboard.readText().then(function (t) {
        if (!t || !t.trim()) {
          aviso.textContent = "Não tem nada copiado ainda. Volte à mensagem, segure o dedo nela e toque em Copiar.";
          aviso.hidden = false; return;
        }
        campo.value = t.slice(0, 4000); aviso.hidden = true; atualizar();
        confirma.scrollIntoView({ behavior: "smooth", block: "center" });
      }).catch(falhou);
    });
    atualizar();
  })();
})();
