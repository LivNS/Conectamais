"""Alertas de demonstração, carregados só quando o banco está vazio.

Servem para a página pública não abrir em branco no plano gratuito do Render, que apaga o
disco a cada deploy. Aparecem marcados como "demonstração" e não citam fontes reais.
"""
from __future__ import annotations

import banco

DEMONSTRACAO = [
    {
        "id": "de0000000000000a",
        "titulo": "Mensagem diz que sua conta será bloqueada e pede para tocar num link",
        "tema": "banco_falso", "tema_rotulo": "Falso contato do banco",
        "resumo_simples": "Golpistas mandam SMS ou WhatsApp em nome do banco falando de compra suspeita "
                          "ou bloqueio. O link leva a uma página falsa que pede senha e dados do cartão.",
        "como_se_proteger": ["Não toque no link.", "Abra o aplicativo do banco por conta própria.",
                             "Na dúvida, ligue para o número no verso do cartão."],
    },
    {
        "id": "de0000000000000b",
        "titulo": "Falso filho ou neto com número novo pede Pix urgente",
        "tema": "pix_parente", "tema_rotulo": "Pedido de dinheiro de falso parente",
        "resumo_simples": "A pessoa diz que trocou de número, usa a foto de alguém da família e logo "
                          "pede dinheiro para uma conta em nome de outra pessoa.",
        "como_se_proteger": ["Ligue para o número antigo do parente.",
                             "Faça uma pergunta que só ele saberia responder.",
                             "Não faça Pix antes de confirmar."],
    },
    {
        "id": "de0000000000000c",
        "titulo": "Pedido do código de 6 dígitos que chegou por SMS",
        "tema": "codigo_verificacao", "tema_rotulo": "Pedido de código de verificação",
        "resumo_simples": "Com esse código, o golpista entra no seu WhatsApp e pede dinheiro aos seus "
                          "contatos fingindo ser você.",
        "como_se_proteger": ["Nunca passe o código para ninguém.",
                             "Ative a confirmação em duas etapas do WhatsApp."],
    },
    {
        "id": "de0000000000000d",
        "titulo": "Aviso de dinheiro a receber do INSS com cobrança de taxa",
        "tema": "inss_beneficios", "tema_rotulo": "Golpe com aposentadoria ou benefício",
        "resumo_simples": "A mensagem promete valores atrasados da aposentadoria, mas pede uma taxa ou "
                          "seus dados para liberar. O INSS não cobra taxa para pagar benefício.",
        "como_se_proteger": ["Consulte só pelo aplicativo Meu INSS ou pelo telefone 135.",
                             "Não pague taxa para receber dinheiro."],
    },
]


def carregar_se_vazio() -> int:
    if not banco.vazio():
        return 0
    for a in DEMONSTRACAO:
        banco.inserir_rascunho({**a, "fonte_nome": "Conteúdo de demonstração", "link_fonte": "",
                                "data_publicacao": "", "precisa_revisar_tema": False,
                                "status": "publicado", "origem": "demonstracao",
                                "criado_em": banco.agora(), "revisado_em": banco.agora()})
    return len(DEMONSTRACAO)
