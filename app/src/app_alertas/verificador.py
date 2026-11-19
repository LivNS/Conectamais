"""Verificador de mensagens suspeitas: motor de regras explicável.

Regras de privacidade (não mudar sem rever a LGPD do projeto):
- o texto recebido é processado só em memória: nunca é gravado, registrado em log ou enviado a terceiros;
- links são lidos como texto: nunca são abertos, baixados ou visitados.

Cada sinal tem peso e uma explicação pronta. A soma dos pesos define o nível.
A resposta nunca diz "é golpe" nem "é seguro": diz quais sinais encontrou.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

TAMANHO_MINIMO = 20          # caracteres; abaixo disso o resultado é inconclusivo
TAMANHO_MAXIMO = 4000        # protege o servidor; mensagens reais são bem menores

LIMITE_MEDIO = 3
LIMITE_ALTO = 6

MARCAS = ("banco", "caixa", "itau", "bradesco", "santander", "nubank", "inter", "sicoob",
          "sicredi", "inss", "gov", "correios", "receita", "detran", "serasa", "pix",
          "horizonte", "whatsapp", "netflix", "mercadolivre", "magalu", "amazon")
ENCURTADORES = ("bit.ly", "tinyurl", "cutt.ly", "t.co/", "is.gd", "rb.gy", "encurtador",
                "shorturl", "ow.ly", "tiny.cc", "s.id/", "u.to/")
TLDS_SUSPEITOS = (".xyz", ".top", ".online", ".site", ".click", ".info", ".live", ".shop",
                  ".icu", ".buzz", ".link", ".app", ".io", ".me", ".cc", ".tk")
DOMINIOS_OFICIAIS = (".gov.br", ".jus.br", ".leg.br", ".mp.br")


@dataclass(frozen=True)
class Sinal:
    id: str
    peso: int
    titulo: str
    explicacao: str
    licao: str
    padroes: tuple[str, ...]


SINAIS: tuple[Sinal, ...] = (
    Sinal("pede_codigo", 5, "Pede código, senha ou token",
          "Nenhum banco, empresa ou órgão pede o código que chega por SMS ou a sua senha. "
          "Quem tem esse código consegue entrar no seu WhatsApp ou na sua conta.",
          "codigo_verificacao",
          (r"(envi|pass|inform|digit|confirm|mand|fal|diga|repass|compartilh)\w*\s+(\w+\s+){0,4}"
           r"(o\s+|a\s+|seu\s+|sua\s+)?(codigo|senha|token|chave de seguranca)",
           r"(codigo|senha|token)\s+(\w+\s+){0,4}(que\s+)?(chegou|recebeu|vai chegar|enviamos|enviado)",
           r"\bsua senha\b", r"\bcodigo de (verificacao|seguranca|confirmacao|acesso)\b",
           r"\b(6|seis) digitos\b")),
    Sinal("numero_novo", 4, "Diz que trocou de número",
          "Golpistas fingem ser um filho, neto ou amigo com \"número novo\" para pedir dinheiro. "
          "Antes de qualquer coisa, ligue para o número antigo da pessoa.",
          "pix_parente",
          (r"troquei (de |o )?(numero|celular|chip)", r"(meu|esse|este) (e o meu )?(numero|zap|whats) novo",
           r"numero novo", r"mudei (de |o )?(numero|celular)", r"salva (esse|este|meu) (numero|contato)",
           r"(celular|telefone) (quebrou|caiu|estragou|foi roubado)", r"perdi (o |meu )?(celular|chip)")),
    Sinal("falso_suporte", 4, "Pede para instalar app ou ligar para uma \"central\"",
          "Pedir para instalar um aplicativo ou dar acesso ao celular é o caminho para o golpista "
          "controlar o aparelho. Banco não pede isso por mensagem.",
          "banco_falso",
          (r"\binstal[ae]\w*", r"baix[ae]\w* (o |este |esse |nosso )?(aplicativo|app)",
           r"acesso remoto", r"anydesk", r"teamviewer", r"central de (seguranca|atendimento|prevencao)",
           r"\bligue (agora )?(para|no)\b", r"nao desligue", r"atualiz\w* (o |seu )?(aplicativo|app)")),
    Sinal("pix_transferencia", 3, "Pede Pix, transferência ou pagamento",
          "Pedido de dinheiro por mensagem merece desconfiança, ainda mais com pressa. "
          "Confirme por outro canal antes de pagar qualquer coisa.",
          "pix_parente",
          (r"\bpix\b", r"\btransfer\w*", r"\bdeposit\w*", r"\bme empresta\w*", r"\bpaga(r)? (uma|um|a|o|essa|esse)\b",
           r"\btaxa de (liberacao|entrega|resgate|desbloqueio|cadastro)\b", r"\bboleto\b")),
    Sinal("premio", 3, "Promete prêmio, brinde ou dinheiro fácil",
          "Prêmio que você não pediu e promoção boa demais são iscas. "
          "Ninguém sorteia quem não se inscreveu.",
          "promocao_falsa",
          (r"\bparabens\b", r"\bpremi\w*", r"\bsortead\w*", r"\bvoce ganhou\b", r"\bganhou (um|uma|r\$)",
           r"\bbrinde\b", r"\bresgat\w*", r"\bcashback\b", r"\bgratis\b", r"\bpromocao\b",
           r"\bvalores a receber\b", r"\bdinheiro esquecido\b")),
    Sinal("dados_pessoais", 3, "Pede dados pessoais",
          "Pedido para confirmar CPF, cartão ou dados cadastrais por mensagem é típico de golpe. "
          "Seu banco já tem esses dados.",
          "banco_falso",
          (r"\bcpf\b", r"(numero|dados) do (seu )?cartao", r"\bcvv\b", r"data de nascimento",
           r"(atualiz|confirm|valid|regulariz)\w* (os |seus |o seu |o )?(dados|cadastro)",
           r"dados cadastrais")),
    Sinal("urgencia", 2, "Cria pressa ou ameaça",
          "Pressa é a principal arma do golpe: ela impede você de pensar e de conferir. "
          "Mensagem verdadeira espera você confirmar.",
          "banco_falso",
          (r"\burgente\w*", r"\bimediatamente\b", r"\bultima (chance|oportunidade)\b",
           r"\bbloquead\w*", r"\bbloqueio\b", r"\bsuspens\w*", r"\bcancelad\w*", r"\bexpira\w*",
           r"\bem ate \d+ ?(h|horas|minutos)\b", r"\bhoje\b", r"\bagora mesmo\b", r"\bevite( (o|a|seu|sua))? \w+",
           r"\bpreciso (muito|urgente)\b", r"\binvas\w*", r"\bclonad\w*", r"\bfraude\w*", r"\bcompra (suspeita|nao reconhecida)\b")),
    Sinal("link", 2, "Tem link",
          "Links em mensagens inesperadas levam a páginas falsas que imitam bancos e lojas. "
          "Não toque: abra o aplicativo oficial por conta própria.",
          "banco_falso",
          (r"https?://\S+", r"\bwww\.\S+",
           r"\b[a-z0-9][a-z0-9-]*(\.[a-z0-9-]+)*\.(com|net|org|br|xyz|top|info|online|site|click|app|io|"
           r"me|ly|cc|tk|live|shop|icu|buzz|link)(\.br)?(/\S*)?\b")),
)

SINAL_LINK_SUSPEITO = Sinal(
    "link_suspeito", 3, "O link parece disfarçado",
    "O endereço usa encurtador ou imita o nome de uma marca num site que não é o oficial. "
    "É assim que páginas falsas enganam.",
    "banco_falso", ())

RE_SENSIVEL = (
    re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"),            # CPF
    re.compile(r"\b(?:\d{4}[ .-]?){3}\d{4}\b"),                  # cartão
    re.compile(r"(?<![\d.,])\d{3}[- ]?\d{3}(?![\d.,])"),        # código de 6 dígitos
)

NIVEIS = {
    "alto": ("Risco alto", "Esta mensagem tem vários sinais fortes de golpe. Não responda, não clique e não pague nada."),
    "medio": ("Risco médio", "Esta mensagem tem sinais de golpe. Confirme por outro canal antes de fazer qualquer coisa."),
    "baixo": ("Risco baixo", "Encontramos poucos sinais de golpe. Mesmo assim, na dúvida, confirme pelo canal oficial."),
    "inconclusivo": ("Não deu para avaliar", "Não encontramos sinais conhecidos de golpe. Isso não quer dizer que a mensagem seja segura."),
}

ACOES_POR_SINAL = {
    "pede_codigo": "Não passe nenhum código ou senha, para ninguém.",
    "numero_novo": "Ligue para o número antigo da pessoa ou faça uma pergunta que só ela saberia.",
    "falso_suporte": "Não instale nada. Desligue e ligue você mesmo para o número no verso do seu cartão.",
    "pix_transferencia": "Não faça Pix nem pagamento antes de confirmar por outro canal.",
    "premio": "Não informe dados nem pague \"taxas\" para receber prêmio.",
    "dados_pessoais": "Não envie CPF, cartão ou dados cadastrais por mensagem.",
    "link": "Não toque no link. Abra o aplicativo oficial ou digite o endereço você mesmo.",
    "link_suspeito": "Não toque no link. Abra o aplicativo oficial ou digite o endereço você mesmo.",
    "urgencia": "Respire: quem tem pressa é o golpista. Você pode conferir com calma.",
}
ACAO_FINAL = "Na dúvida, mostre a mensagem para alguém de confiança e apague em seguida."


@dataclass
class Resultado:
    nivel: str
    rotulo: str
    resumo: str
    pontos: int
    sinais: list[dict] = field(default_factory=list)
    acoes: list[str] = field(default_factory=list)
    trechos: list[tuple[int, int]] = field(default_factory=list)
    licao_sugerida: str | None = None
    tem_dado_sensivel: bool = False
    motivo_inconclusivo: str | None = None

    def para_dict(self) -> dict:
        """Versão segura para a API: não inclui o texto, só posições dos trechos."""
        return {
            "nivel": self.nivel, "rotulo": self.rotulo, "resumo": self.resumo, "pontos": self.pontos,
            "sinais": self.sinais, "acoes": self.acoes,
            "trechos": [list(t) for t in self.trechos],
            "licao_sugerida": self.licao_sugerida, "tem_dado_sensivel": self.tem_dado_sensivel,
            "motivo_inconclusivo": self.motivo_inconclusivo,
        }


def normalizar(texto: str) -> str:
    """Minúsculas e sem acentos, mantendo o mesmo comprimento (as posições valem no texto original)."""
    return "".join((unicodedata.normalize("NFD", c)[:1] or c).lower()[:1] or c for c in texto)


def _encontrar(padroes: tuple[str, ...], norm: str) -> list[tuple[int, int]]:
    achados = []
    for p in padroes:
        achados += [m.span() for m in re.finditer(p, norm)]
    return achados


def _link_suspeito(links: list[str]) -> bool:
    for link in links:
        l = link.lower().rstrip(".,;)!")
        if any(e in l for e in ENCURTADORES):
            return True
        dominio = re.sub(r"^https?://", "", l).split("/")[0]
        if dominio.endswith(DOMINIOS_OFICIAIS):
            continue
        tem_marca = any(m in dominio for m in MARCAS)
        estranho = "-" in dominio or any(dominio.endswith(t) for t in TLDS_SUSPEITOS) \
            or re.search(r"\d", dominio) is not None
        if tem_marca and estranho:
            return True
        if any(dominio.endswith(t) for t in TLDS_SUSPEITOS):
            return True
    return False


def _juntar(trechos: list[tuple[int, int]]) -> list[tuple[int, int]]:
    juntos: list[list[int]] = []
    for a, b in sorted(trechos):
        if juntos and a <= juntos[-1][1]:
            juntos[-1][1] = max(juntos[-1][1], b)
        else:
            juntos.append([a, b])
    return [(a, b) for a, b in juntos]


def nivel_por_pontos(pontos: int) -> str:
    if pontos >= LIMITE_ALTO:
        return "alto"
    if pontos >= LIMITE_MEDIO:
        return "medio"
    if pontos > 0:
        return "baixo"
    return "inconclusivo"


def analisar(texto: str) -> Resultado:
    texto = (texto or "")[:TAMANHO_MAXIMO]
    norm = normalizar(texto)
    sensivel = any(r.search(texto) for r in RE_SENSIVEL)

    if len(texto.strip()) < TAMANHO_MINIMO:
        rot, res = NIVEIS["inconclusivo"]
        return Resultado("inconclusivo", rot, res, 0, tem_dado_sensivel=sensivel,
                         acoes=[ACAO_FINAL],
                         motivo_inconclusivo="A mensagem é curta demais. Cole o texto completo que você recebeu.")

    encontrados: list[tuple[Sinal, list[tuple[int, int]]]] = []
    for s in SINAIS:
        achados = _encontrar(s.padroes, norm)
        if achados:
            encontrados.append((s, achados))

    links = [texto[a:b] for s, ach in encontrados if s.id == "link" for a, b in ach]
    if links and _link_suspeito(links):
        encontrados.append((SINAL_LINK_SUSPEITO, []))

    pontos = sum(s.peso for s, _ in encontrados)
    nivel = nivel_por_pontos(pontos)
    rot, res = NIVEIS[nivel]

    ordenados = sorted(encontrados, key=lambda x: -x[0].peso)
    sinais = [{"id": s.id, "titulo": s.titulo, "explicacao": s.explicacao, "peso": s.peso, "licao": s.licao}
              for s, _ in ordenados]
    acoes = []
    for s, _ in ordenados:
        a = ACOES_POR_SINAL[s.id]
        if a not in acoes:
            acoes.append(a)
    acoes = acoes[:3] + [ACAO_FINAL]
    trechos = _juntar([t for _, ach in encontrados for t in ach])

    return Resultado(
        nivel, rot, res, pontos, sinais, acoes, trechos,
        licao_sugerida=ordenados[0][0].licao if ordenados else None,
        tem_dado_sensivel=sensivel,
        motivo_inconclusivo=None if nivel != "inconclusivo" else
        "Não encontramos sinais que conhecemos. Golpes novos aparecem sempre: na dúvida, confirme pelo canal oficial.",
    )


def partes_destacadas(texto: str, trechos: list[tuple[int, int]]) -> list[tuple[str, bool]]:
    """Divide o texto em pedaços (texto, destacado?) para a tela marcar onde estão os sinais."""
    partes, pos = [], 0
    for a, b in trechos:
        if a > pos:
            partes.append((texto[pos:a], False))
        partes.append((texto[a:b], True))
        pos = b
    if pos < len(texto):
        partes.append((texto[pos:], False))
    return partes
