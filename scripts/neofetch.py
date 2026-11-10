#!/usr/bin/env python3
"""Gera dark_mode.svg e light_mode.svg: card estilo neofetch dentro de uma janela de terminal.

Roda todo dia pela Action .github/workflows/neofetch.yml.
Para rodar localmente (precisa do GitHub CLI logado):

    GH_TOKEN=$(gh auth token) python scripts/neofetch.py

Só usa a biblioteca padrão do Python.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

USUARIO = "rafavieira1"
NASCIMENTO = date(2002, 12, 3)
FUSO = timezone(timedelta(hours=-3))  # horário de Brasília

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
RETRATO = AQUI / "retrato.txt"

# Dados fixos do card. Os números do GitHub são buscados na API.
SISTEMA = [
    ("OS", "Windows 11"),
    ("Uptime", None),  # calculado a partir de NASCIMENTO
    ("Host", "UTFPR Medianeira"),
    ("Kernel", "Ciência da Computação"),
    ("IDE", "VS Code"),
]
STACK = [
    ("Linguagens.Código", "TypeScript, Python, Java"),
    ("Linguagens.Web", "React, HTML, CSS"),
    ("Ferramentas", "Git, Docker"),
    ("Origem", "Campinas, SP"),
]
CONTATO = [
    ("Site", "rafavieiradev.netlify.app"),
    ("Email", "rafasvieira01@gmail.com"),
    ("LinkedIn", "rafael-silva-vieira"),
]

TEMAS = {
    "dark": {
        "fundo": "#161b22", "barra": "#1f2630", "borda": "#30363d",
        "arte": "#c9d1d9", "titulo": "#e6edf3", "chave": "#ffa657", "valor": "#a5d6ff",
        "numero": "#79c0ff", "ponto": "#616e7f", "janela": "#7d8590",
        "barras": ["#21262d", "#0c2d6b", "#1158c7", "#388bfd", "#79c0ff"],
    },
    "light": {
        "fundo": "#f6f8fa", "barra": "#e6eaef", "borda": "#d1d9e0",
        "arte": "#24292f", "titulo": "#1f2328", "chave": "#953800", "valor": "#0a3069",
        "numero": "#0550ae", "ponto": "#8c959f", "janela": "#59636e",
        "barras": ["#e1e4e8", "#cae8ff", "#80ccff", "#218bff", "#0550ae"],
    },
}
SEMAFORO = ("#ff5f57", "#febc2e", "#28c840")

# Geometria (px). Larguras de caractere fixas + textLength = alinhamento igual em qualquer sistema.
FS, CW, LH = 16, 9.6, 20  # texto da direita
AFS, ACW, ALH = 8, 4.8, 9.6  # retrato
COL = 56  # largura da coluna da direita, em caracteres
BARRA_H = 36
MARGEM = 24
FONTES = ("'JetBrains Mono','Cascadia Mono','SF Mono',Menlo,Consolas,"
          "'DejaVu Sans Mono','Liberation Mono',monospace")
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

# ---------------------------------------------------------------- API


def graphql(query: str, variaveis: dict, token: str) -> dict:
    corpo = json.dumps({"query": query, "variables": variaveis}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=corpo,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": f"{USUARIO}-neofetch"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        dados = json.load(resp)
    if dados.get("errors"):
        raise RuntimeError(f"Erro na API do GitHub: {dados['errors']}")
    return dados["data"]["user"]


CONSULTA = """
query($login: String!) {
  user(login: $login) {
    createdAt
    pullRequests { totalCount }
    publicos: repositories(ownerAffiliations: OWNER, privacy: PUBLIC) { totalCount }
    proprios: repositories(ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false, first: 100) {
      nodes { languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } } }
    }
    contributionsCollection {
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
    }
  }
}
"""


def total_historico(desde: datetime, agora: datetime, token: str) -> int:
    """Soma as contribuições ano a ano (a API aceita no máximo 1 ano por consulta)."""
    partes = []
    for ano in range(desde.year, agora.year + 1):
        fim = agora.strftime("%Y-%m-%dT%H:%M:%SZ") if ano == agora.year else f"{ano}-12-31T23:59:59Z"
        partes.append(f'a{ano}: contributionsCollection(from: "{ano}-01-01T00:00:00Z", to: "{fim}") '
                      "{ contributionCalendar { totalContributions } }")
    dados = graphql("query($login: String!) { user(login: $login) { " + " ".join(partes) + " } }",
                    {"login": USUARIO}, token)
    return sum(v["contributionCalendar"]["totalContributions"] for v in dados.values())


def coletar(token: str) -> dict:
    u = graphql(CONSULTA, {"login": USUARIO}, token)
    agora = datetime.now(timezone.utc)
    criado = datetime.fromisoformat(u["createdAt"].replace("Z", "+00:00"))

    cal = u["contributionsCollection"]["contributionCalendar"]
    dias = [d["contributionCount"] for w in cal["weeks"] for d in w["contributionDays"]]
    semanas = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in cal["weeks"]]
    maior = atual = 0
    for n in dias:
        atual = atual + 1 if n > 0 else 0
        maior = max(maior, atual)

    bytes_por_lingua: dict[str, int] = {}
    for repo in u["proprios"]["nodes"]:
        for e in repo["languages"]["edges"]:
            bytes_por_lingua[e["node"]["name"]] = bytes_por_lingua.get(e["node"]["name"], 0) + e["size"]
    total_bytes = sum(bytes_por_lingua.values()) or 1
    top = sorted(bytes_por_lingua.items(), key=lambda kv: -kv[1])[:3]

    primeiro_dia = cal["weeks"][0]["contributionDays"][0]["date"]
    return {
        "repos": u["publicos"]["totalCount"],
        "prs": u["pullRequests"]["totalCount"],
        "criado": criado,
        "ano_total": cal["totalContributions"],
        "historico": total_historico(criado, agora, token),
        "maior_sequencia": maior,
        "linguas": [(nome, round(b * 100 / total_bytes)) for nome, b in top],
        "semanas": semanas,
        "inicio": date.fromisoformat(primeiro_dia),
        "fim": agora.astimezone(FUSO).date(),
    }

# ---------------------------------------------------------------- formatação


def plural(n: int, um: str, varios: str) -> str:
    return f"{n} {um if n == 1 else varios}"


def uptime(hoje: date) -> str:
    anos = hoje.year - NASCIMENTO.year
    meses = hoje.month - NASCIMENTO.month
    dias = hoje.day - NASCIMENTO.day
    if dias < 0:
        meses -= 1
        dias += (hoje.replace(day=1) - timedelta(days=1)).day
    if meses < 0:
        anos -= 1
        meses += 12
    return f"{plural(anos, 'ano', 'anos')}, {plural(meses, 'mês', 'meses')}, {plural(dias, 'dia', 'dias')}"


def milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def mes_ano(d: date) -> str:
    return f"{MESES[d.month - 1]} {d.year}"

# ---------------------------------------------------------------- linhas da coluna direita
# Cada linha é uma lista de (classe, texto) com exatamente COL caracteres no total.


def titulo(t: str) -> list:
    return [("titulo", t), ("ponto", " " + "─" * (COL - len(t) - 1))]


def secao(t: str) -> list:
    return [("ponto", "─ "), ("titulo", t), ("ponto", " " + "─" * (COL - len(t) - 3))]


def kv(chave: str, valor: str, classe: str = "valor") -> list:
    pontos = COL - 5 - len(chave) - len(valor)
    if pontos < 1:
        raise ValueError(f"Linha grande demais para a coluna: {chave}: {valor}")
    return [("ponto", ". "), ("chave", chave + ":"), ("ponto", " " + "." * pontos + " "), (classe, valor)]


VAZIO = [("ponto", ".")]


def montar_linhas(d: dict) -> list:
    sistema = [kv(k, v if v is not None else uptime(d["fim"])) for k, v in SISTEMA]
    linguas = " · ".join(f"{nome} {pct}%" for nome, pct in d["linguas"])
    return [
        titulo(f"{USUARIO}@github"),
        *sistema,
        VAZIO,
        *[kv(k, v) for k, v in STACK],
        VAZIO,
        secao("Contato"),
        *[kv(k, v) for k, v in CONTATO],
        VAZIO,
        secao("GitHub"),
        kv("Repos públicos", str(d["repos"]), "numero"),
        kv("Pull requests", str(d["prs"]), "numero"),
        kv("Contribuições (total)", milhar(d["historico"]), "numero"),
        kv("Membro desde", mes_ano(d["criado"].date())),
        VAZIO,
        secao("Últimos 12 meses"),
        kv("Contribuições", milhar(d["ano_total"]), "numero"),
        kv("Maior sequência", plural(d["maior_sequencia"], "dia", "dias"), "numero"),
        kv("Linguagens", linguas),
    ]

# ---------------------------------------------------------------- SVG


def texto(x: float, y: float, partes: list, cw: float, classe: str, extra: str = "") -> str:
    n = sum(len(t) for _, t in partes)
    spans = "".join(f'<tspan class="{c}">{escape(t)}</tspan>' for c, t in partes)
    return (f'<text x="{x:g}" y="{y:g}" class="{classe}" textLength="{n * cw:g}"{extra}>'
            f"{spans}</text>")


def gerar_svg(d: dict, tema: dict, retrato: list) -> str:
    art_w = max(map(len, retrato)) * ACW
    art_h = (len(retrato) - 1) * ALH
    col_x = MARGEM + art_w + 40
    largura = round(col_x + COL * CW + MARGEM)
    topo = BARRA_H + 64  # primeira linha do retrato
    prompt_final = topo + art_h + 44
    altura = round(prompt_final + 22)

    linhas = montar_linhas(d)
    grafico_h = 16 + 44 + 18
    bloco_h = (len(linhas) - 1) * LH + grafico_h
    y0 = topo + max(0, (art_h - bloco_h) / 2) + 4

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
        f'viewBox="0 0 {largura} {altura}" xml:space="preserve" role="img" '
        f'aria-labelledby="t">',
        f'<title id="t">{USUARIO}@github: neofetch de Rafael Vieira</title>',
        "<style>",
        f"text{{font-family:{FONTES};white-space:pre}}",
        f".a{{font-size:{AFS}px;fill:{tema['arte']}}}",
        f".l{{font-size:{FS}px}}",
        f".w{{font-size:13px;fill:{tema['janela']}}}",
        f".titulo{{fill:{tema['titulo']};font-weight:600}}",
        f".chave{{fill:{tema['chave']}}}.valor{{fill:{tema['valor']}}}",
        f".numero{{fill:{tema['numero']}}}.ponto{{fill:{tema['ponto']}}}.arte{{fill:{tema['arte']}}}",
        ".cursor{animation:pisca 1.1s steps(1) infinite}",
        "@keyframes pisca{50%{fill-opacity:0}}",
        "@media (prefers-reduced-motion:reduce){.cursor{animation:none}}",
        "</style>",
        '<defs><clipPath id="janela">'
        f'<rect x="0.5" y="0.5" width="{largura - 1}" height="{altura - 1}" rx="10"/></clipPath></defs>',
        f'<rect x="0.5" y="0.5" width="{largura - 1}" height="{altura - 1}" rx="10" fill="{tema["fundo"]}"/>',
        f'<rect width="{largura}" height="{BARRA_H}" fill="{tema["barra"]}" clip-path="url(#janela)"/>',
        f'<line x1="0" y1="{BARRA_H + 0.5}" x2="{largura}" y2="{BARRA_H + 0.5}" stroke="{tema["borda"]}"/>',
        *[f'<circle cx="{22 + i * 20}" cy="{BARRA_H / 2:g}" r="6" fill="{cor}"/>' for i, cor in enumerate(SEMAFORO)],
    ]
    titulo_janela = f"{USUARIO}@github: ~"
    out.append(f'<text x="{largura / 2:g}" y="{BARRA_H / 2 + 5:g}" class="w" text-anchor="middle">'
               f"{escape(titulo_janela)}</text>")

    prompt = [("valor", f"{USUARIO}@github"), ("ponto", ":~$ ")]
    out.append(texto(MARGEM, BARRA_H + 32, prompt + [("arte", "neofetch")], CW, "l"))

    for i, linha in enumerate(retrato):
        if linha.strip():
            out.append(texto(MARGEM, topo + i * ALH, [("arte", linha)], ACW, "a"))

    for i, linha in enumerate(linhas):
        out.append(texto(col_x, y0 + i * LH, linha, CW, "l"))

    # Mini gráfico: contribuições por semana nos últimos 12 meses
    semanas = d["semanas"]
    base = y0 + (len(linhas) - 1) * LH + 16 + 44
    passo = COL * CW / len(semanas)
    maximo = max(semanas) or 1
    for i, v in enumerate(semanas):
        if v == 0:
            h, nivel = 2, 0
        else:
            frac = v / maximo
            h = max(4, round(44 * frac ** 0.6))
            nivel = 1 if frac < 0.25 else 2 if frac < 0.5 else 3 if frac < 0.75 else 4
        out.append(f'<rect x="{col_x + i * passo:.1f}" y="{base - h:.1f}" width="{passo - 3:.1f}" '
                   f'height="{h}" rx="1.5" fill="{tema["barras"][nivel]}"/>')
    rotulo_ini, rotulo_fim = mes_ano(d["inicio"]), mes_ano(d["fim"])
    out.append(texto(col_x, base + 18, [("ponto", rotulo_ini)], 7.2, "l", ' style="font-size:12px"'))
    out.append(texto(col_x + COL * CW - len(rotulo_fim) * 7.2, base + 18, [("ponto", rotulo_fim)], 7.2, "l",
                     ' style="font-size:12px"'))

    out.append(texto(MARGEM, prompt_final, prompt + [("valor cursor", "█")], CW, "l"))
    out.append(f'<rect x="0.5" y="0.5" width="{largura - 1}" height="{altura - 1}" rx="10" fill="none" '
               f'stroke="{tema["borda"]}"/>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> int:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Defina GH_TOKEN (ex.: GH_TOKEN=$(gh auth token) python scripts/neofetch.py)", file=sys.stderr)
        return 1
    retrato = RETRATO.read_text(encoding="utf-8").rstrip("\n").split("\n")
    dados = coletar(token)
    for nome, tema in TEMAS.items():
        (RAIZ / f"{nome}_mode.svg").write_text(gerar_svg(dados, tema, retrato), encoding="utf-8")
    print(f"ok: {milhar(dados['ano_total'])} contribuições em 12 meses, "
          f"{milhar(dados['historico'])} no total, maior sequência {dados['maior_sequencia']} dias")
    return 0


if __name__ == "__main__":
    sys.exit(main())
