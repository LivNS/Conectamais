# App do Conecta+ (MVP, versão 2)

App web para pessoas 60+: **aprender a usar o celular** praticando sem risco, **conferir se uma mensagem é golpe** e **conhecer os golpes** (os de sempre e os novos, trazidos pelo robô de RPA e aprovados por uma pessoa). A página **Impacto** mostra números reais e anônimos.

## Telas

| Endereço | O que faz |
| --- | --- |
| `/` | Início com três caminhos: Aprender o celular, É golpe?, Golpes do momento |
| `/aprender` | Nível 1 (9 lições do celular) e Nível 2 (teste rápido, 2 aulas, 4 aulas de golpe, teste final); progresso no aparelho |
| `/aprender/celular/toque` | Treino seguro de tocar, segurar e arrastar |
| `/aprender/celular/audio` | Simulador: achar a conversa, segurar o microfone, enviar |
| `/aprender/celular/copiar` | Simulador: segurar, copiar, segurar, colar (prepara para o verificador) |
| `/aprender/celular/{letra,ligar,volume,video,bloquear,icone}` | Passo a passo com versão Android e iPhone (detectado sozinho, dá para trocar) |
| `/aprender/aula/{link,senha}` | Aulas do Nível 2: telas com figura e uma pergunta |
| `/aprender/{licao}` e `/aprender/teste/{pre,pos}` | Aulas de golpe com quiz e testes que medem o ganho de conhecimento |
| `/verificar` | Botão "Colar a mensagem" (lê a área de transferência) e caixa para colar; resultado em linguagem simples |
| `/golpes` | Golpes novos (alertas aprovados) e 12 golpes de sempre; `/golpes/{id}` e `/golpes/alerta/{id}` explicam cada um |
| `/revisao` | Login do revisor; aprovar ou rejeitar rascunhos do robô |
| `/impacto` | Ganho de conhecimento, lições do celular concluídas, uso do verificador |
| `/privacidade` | Política em linguagem simples e "Apagar meus dados" |

`/alertas` (endereço antigo) redireciona para `/golpes`.

## Acessibilidade e UX

- Letra base de 22 px, botão "AA" com 3 tamanhos (fica salvo no aparelho), fonte Atkinson Hyperlegible servida pelo próprio app.
- Uma frase por tela, botões de pelo menos 56 px, "Voltar" escrito em toda tela, botão "Ouvir" (voz do próprio celular).
- Amarelo sempre quer dizer "olhe aqui": trecho suspeito na mensagem ou onde tocar no treino.
- Treinos aceitam dedo trêmulo: segurar não cancela se o dedo escorrega, e o teclado também funciona.
- Manifesto e ícones para "Adicionar à tela inicial" (a lição "Conecta+ na tela" ensina a fazer).

## Rodar localmente

```bash
cd app
pip install -r requirements-dev.txt
python -m pytest tests -q            # 90 testes
cd src/app_alertas
DATABASE_PATH=../../dados.sqlite3 RPA_API_TOKEN=troque ADMIN_USUARIO=revisor ADMIN_SENHA=troque \
  uvicorn main:app --reload
```

Abra http://localhost:8000.

## Variáveis de ambiente

| Variável | Para quê |
| --- | --- |
| `DATABASE_PATH` | Arquivo SQLite (alertas e eventos anônimos) |
| `RPA_API_TOKEN` | Token que o robô envia em `Authorization: Bearer` |
| `ADMIN_USUARIO`, `ADMIN_SENHA` | Login da tela `/revisao` |
| `APP_NOME` | Nome exibido (padrão "Conecta+") |
| `ALERTAS_DEMONSTRACAO` | `0` desliga os 4 alertas de demonstração que aparecem com o banco vazio |
| `PORT` | Porta do container (o Render define sozinho) |

## Contrato com o robô (inalterado)

`POST /api/alertas/rascunhos` com `Authorization: Bearer {RPA_API_TOKEN}` e os campos `id, titulo, tema, tema_rotulo, resumo_simples, como_se_proteger[], fonte_nome, link_fonte, data_publicacao, precisa_revisar_tema, status, origem, criado_em`. Respostas: 201 (recebido), 409 (já existia), 401 (token), 422 (inválido). O status gravado é sempre `pendente_revisao`, mesmo que o robô envie outro: nada se publica sem a revisão humana.

Outros endpoints: `GET /api/alertas`, `GET /api/alertas/pendentes` (revisor), `POST /api/alertas/{id}/aprovar` e `/rejeitar` (revisor), `POST /api/verificar`, `POST /api/eventos`, `DELETE /api/eventos/{aparelho}`, `GET /api/impacto`, `GET /saude`.

## Privacidade

- O texto colado é analisado em memória e descartado; um teste confere que ele não chega ao banco nem aos logs.
- Links nunca são abertos.
- Eventos guardam só contagens e um identificador aleatório criado no aparelho.
- A fonte (Atkinson Hyperlegible, licença OFL) é servida pelo próprio app: nenhuma página faz pedidos a terceiros.

## Atenção no Render (plano gratuito)

O disco é apagado a cada deploy. Depois dos testes com pessoas 60+, salve o JSON de `/api/impacto` e um print de `/impacto`, e não faça deploy entre os testes e a gravação do pitch.
