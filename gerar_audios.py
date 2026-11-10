#!/usr/bin/env python3
"""
Gera MP3 (voz em português) a partir de uma lei compilada do site do Planalto,
um arquivo por capítulo (Títulos sem capítulos viram um arquivo próprio).

Requisitos (num venv):  pip install edge-tts beautifulsoup4

Uso:
    python3 gerar_audios.py ARQUIVO_OU_URL --sigla LRP --nome "Lei 6.015, de 1973, Lei de Registros Públicos"
    python3 gerar_audios.py l6015.htm --sigla LRP --nome "..." --so-texto   # só gera os .txt para revisar

Os arquivos são numerados a partir de --inicio (padrão: próximo número livre em audios/),
para que várias leis possam conviver na mesma pasta em sequência.
"""

import argparse
import asyncio
import os
import re
import sys
import urllib.request

from bs4 import BeautifulSoup

VOZ_PADRAO = "pt-BR-AntonioNeural"
PASTA_AUDIOS = "audios"

# ---------------------------------------------------------------- download

def ler_html(origem):
    if re.match(r"https?://", origem):
        req = urllib.request.Request(origem, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/130 Safari/537.36",
            "Accept-Language": "pt-BR",
        })
        with urllib.request.urlopen(req, timeout=60) as r:
            dados = r.read()
    else:
        with open(origem, "rb") as f:
            dados = f.read()
    try:
        return dados.decode("utf-8")
    except UnicodeDecodeError:
        return dados.decode("windows-1252")

# ---------------------------------------------------------------- estrutura

BLOCOS = ["p", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "td"]
RE_TITULO = re.compile(r"^T[ÍI]TULO\s+([IVXLC]+(?:-[A-Z])?)\b\s*(.*)$", re.I)
RE_CAPITULO = re.compile(r"^CAP[ÍI]TULO\s+([IVXLC]+(?:-[A-Z])?)\b\s*(.*)$", re.I)
RE_FIM = re.compile(r"^Bras[íi]lia,\s+\d")


def blocos_de_texto(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    for el in soup.find_all(BLOCOS):
        if el.find(BLOCOS):          # evita contar texto de blocos aninhados duas vezes
            continue
        for br in el.find_all("br"):
            br.replace_with("\n")
        txt = el.get_text().replace("\xa0", " ")
        linhas = [re.sub(r"\s+", " ", l).strip() for l in txt.split("\n")]
        linhas = [l for l in linhas if l]
        if linhas:
            yield linhas


def limpar_nome(n):
    n = re.sub(rf"\(\s*(?:{NOTAS}|Revogad|Vetad)[^)]*(?:\)|$)", " ", n, flags=re.I)
    return re.sub(r"\s+", " ", n).strip(" .")


def dividir(html):
    """Retorna lista de episódios: dict(titulo, capitulo, nome_tit, nome_cap, paragrafos)."""
    eps = []
    titulo = nome_tit = None
    atual = None
    iniciado = False
    pendente_nome = None  # "tit" ou "cap" quando o nome vem no bloco seguinte

    for linhas in blocos_de_texto(html):
        primeira = linhas[0]
        texto = " ".join(linhas)
        mt, mc = RE_TITULO.match(primeira), RE_CAPITULO.match(primeira)

        if mt:
            iniciado = True
            titulo = mt.group(1).upper()
            nome_tit = limpar_nome(mt.group(2) + " " + " ".join(linhas[1:]))
            pendente_nome = None if nome_tit else "tit"
            atual = {"titulo": titulo, "nome_tit": nome_tit, "capitulo": None,
                     "nome_cap": "", "paragrafos": []}
            eps.append(atual)
            continue
        if not iniciado:
            continue
        if RE_FIM.match(texto):
            break
        if mc:
            nome_cap = limpar_nome(mc.group(2) + " " + " ".join(linhas[1:]))
            if atual["capitulo"] is None and not any(p.startswith("Art") for p in atual["paragrafos"]):
                # primeiro capítulo do título: mesmo episódio que o cabeçalho do título
                atual["capitulo"], atual["nome_cap"] = mc.group(1).upper(), nome_cap
            else:
                atual = {"titulo": titulo, "nome_tit": nome_tit, "capitulo": mc.group(1).upper(),
                         "nome_cap": nome_cap, "paragrafos": []}
                eps.append(atual)
            pendente_nome = None if nome_cap else "cap"
            continue
        if pendente_nome and not texto.startswith("Art"):
            if pendente_nome == "tit":
                atual["nome_tit"] = nome_tit = limpar_nome(texto)
            else:
                atual["nome_cap"] = limpar_nome(texto)
            pendente_nome = None
            continue
        pendente_nome = None
        atual["paragrafos"].append(texto)

    return [e for e in eps if e["paragrafos"]]

# ---------------------------------------------------------------- fala

ORD_M = ["", "primeiro", "segundo", "terceiro", "quarto", "quinto",
         "sexto", "sétimo", "oitavo", "nono"]
ORD_F = [o[:-1] + "a" if o else o for o in ORD_M]
ROMANOS = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}

NOTAS = (r"Reda[çc][ãa]o dada|Inclu[íi]d[oa]|Acrescid[oa]|Acrescentad[oa]|Renumerad[oa]|"
         r"Vide\b|Vig[êe]ncia|Regulamento|Produ[çc][ãa]o de efeito|Revigorad[oa]|"
         r"Com reda[çc][ãa]o|Promulga[çc][ãa]o|Convertid[oa]|Express[ãa]o|Eficácia|Suspens")


def romano(s):
    total = 0
    for i, c in enumerate(s):
        v = ROMANOS[c]
        total += -v if i + 1 < len(s) and ROMANOS[s[i + 1]] > v else v
    return total


def romanos_apos_palavra(texto):
    palavras = r"(?:incisos?|itens|item|cap[íi]tulos?|t[íi]tulos?|se[çc][õo]es|se[çc][ãa]o|subse[çc][ãa]o|livros?)"
    seq = r"[IVXLC]+(?:\s*(?:,|e|a|ou)\s*[IVXLC]+)*"

    def troca(m):
        nums = re.sub(r"\b[IVXLC]+\b", lambda r: str(romano(r.group(0))), m.group(2))
        return m.group(1) + nums
    return re.sub(rf"\b({palavras}\s+)({seq})\b", troca, texto, flags=re.I)


def para_fala(t):
    # notas de alteração legislativa
    t = re.sub(r"(\d)(?:\.\s?o|°|o)(?=[\s.,;:)\-]|$)", r"\1º", t)
    t = re.sub(r"\(\s*Revogad[oa][^)]*(?:\)|$)", " Revogado. ", t, flags=re.I)
    t = re.sub(r"\(\s*Vetad[oa][^)]*(?:\)|$)", " Vetado. ", t, flags=re.I)
    t = re.sub(rf"\(\s*(?:{NOTAS})[^)]*(?:\)|$)", " ", t, flags=re.I)
    t = re.sub(r"\s+([.,;:])", r"\1", t)
    t = re.sub(r"\.[\s.;,:]*(?=\s|$)", ".", t)
    t = re.sub(r"[;:,]\s*$", ".", t) if re.search(r"(Revogado|Vetado)[;:,]\s*$", t) else t

    # dispositivo no início do parágrafo
    t = re.sub(r"^([IVXLC]+)\s*[-–—]\s*", lambda m: f"Inciso {romano(m.group(1))}: ", t)
    t = re.sub(r"^Par[áa]grafo [úu]nico\.?\s*", "Parágrafo único. ", t)

    # artigos e parágrafos
    def art(m, palavra):
        n, suf = m.group(1).replace(".", ""), m.group(2) or ""
        num = ORD_M[int(n)] if m.group(3) and int(n) < 10 else n
        suf = " " + suf.strip("-–") if suf else ""
        return f"{palavra} {num}{suf}"
    t = re.sub(r"\bArts?\.\s*", lambda m: "Artigos " if m.group(0).startswith("Arts") else "Art. ", t)
    t = re.sub(r"\bArt\.\s*([\d.]+)(-[A-Z]\b)?(º|o\b)?\.?",
               lambda m: art(m, "Artigo") + ".", t)
    t = re.sub(r"^((?:Artigo) [^.]+\.)\s*[-–—]\s*", r"\1 ", t)
    t = re.sub(r"\barts\.\s*", "artigos ", t)
    t = re.sub(r"\bart\.\s*([\d.]+)(-[A-Z]\b)?(º)?", lambda m: art(m, "artigo"), t)
    t = re.sub(r"^§\s*([\d.]+)(-[A-Z]\b)?(º)?\.?", lambda m: art(m, "Parágrafo") + ".", t)
    t = re.sub(r"^(Parágrafo [^.]+\.)\s*[-–—]\s*", r"\1 ", t)
    t = re.sub(r"§§\s*", "parágrafos ", t)
    t = re.sub(r"§\s*([\d.]+)(-[A-Z]\b)?(º)?", lambda m: art(m, "parágrafo"), t)

    # ordinais e abreviações
    t = re.sub(r"\b([1-9])º", lambda m: ORD_M[int(m.group(1))], t)
    t = re.sub(r"\b([1-9])ª", lambda m: ORD_F[int(m.group(1))], t)
    # "15 (quinze) dias" / "trinta (30) dias": fala o número uma vez só
    ext = r"[a-zà-ÿ][a-zà-ÿ ,\-]*"
    t = re.sub(rf"\b(?:R\$\s*)?\d[\d.,]*\s*(%|m²)?\s*\(({ext})\)", r"\2", t)
    t = re.sub(rf"\b({ext[:-1]}*?)\s*\(\d[\d.,]*\)", r"\1", t)
    t = re.sub(r"\bn[º°]s\.?\s*", "números ", t)
    t = re.sub(r"\bn[º°]\.?\s*([IVXLC]+)\b", lambda m: f"número {romano(m.group(1))}", t)
    t = re.sub(r"\bn[º°o]\.?\s*(?=\d)", "número ", t, flags=re.I)
    t = re.sub(r"\bn\.º\s*", "número ", t)
    t = romanos_apos_palavra(t)
    t = re.sub(r"\bcaput\b", "cáput", t)

    return re.sub(r"\s+", " ", t).strip()


RE_REVOGADO = re.compile(r"^(Artigo|Parágrafo|Inciso) ([^.:]+)[.:] (Revogado|Vetado)\.$")
PLURAL = {"Artigo": "Artigos", "Parágrafo": "Parágrafos", "Inciso": "Incisos"}


def agrupar_revogados(falas):
    saida, run = [], []

    def fecha():
        if len(run) == 1:
            saida.append(run[0][3])
        elif run:
            tipo, ini, est = run[0][0], run[0][1], run[0][2].lower()
            saida.append(f"{PLURAL[tipo]} {ini} a {run[-1][1]}: {est[:-1]}os.")
        run.clear()

    for f in falas:
        m = RE_REVOGADO.match(f)
        if m and (not run or (run[0][0] == m.group(1) and run[0][2] == m.group(3))):
            run.append((m.group(1), m.group(2), m.group(3), f))
            continue
        fecha()
        if m:
            run.append((m.group(1), m.group(2), m.group(3), f))
        else:
            saida.append(f)
    fecha()
    return saida


def roteiro(ep, nome_lei):
    partes = [f"{nome_lei}."]
    partes.append(f"Título {romano(ep['titulo'].split('-')[0])}. {ep['nome_tit']}.")
    if ep["capitulo"]:
        partes.append(f"Capítulo {romano(ep['capitulo'].split('-')[0])}. {ep['nome_cap'].capitalize() if ep['nome_cap'].isupper() else ep['nome_cap']}.")
    falas = [f for f in (para_fala(p) for p in ep["paragrafos"]) if f and f != "."]
    partes += agrupar_revogados(falas)
    return "\n\n".join(partes)


def nome_arquivo(num, sigla, ep):
    rot = f"Título {ep['titulo']}"
    nome = ep["nome_tit"]
    if ep["capitulo"]:
        rot += f", Cap. {ep['capitulo']}"
        nome = ep["nome_cap"]
    nome = re.sub(r'[\\/:*?"<>|]', "", nome).strip(" .")
    if nome.isupper():
        nome = nome.capitalize()
    return f"{num:03d} - {sigla} {rot} - {nome}"

# ---------------------------------------------------------------- main

async def falar(texto, destino, voz, velocidade):
    import edge_tts
    tmp = destino + ".part"
    for tentativa in range(4):
        try:
            await edge_tts.Communicate(texto, voz, rate=velocidade).save(tmp)
            os.replace(tmp, destino)
            return
        except Exception as e:
            print(f"   erro ({e}); tentando de novo...", file=sys.stderr)
            await asyncio.sleep(5 * (tentativa + 1))
    raise RuntimeError(f"falhou: {destino}")


def proximo_numero():
    nums = [int(m.group(1)) for f in os.listdir(PASTA_AUDIOS)
            if (m := re.match(r"(\d{3})", f))]
    return max(nums, default=0) + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("origem", help="URL do Planalto ou arquivo .htm salvo")
    ap.add_argument("--sigla", required=True, help="ex.: LRP")
    ap.add_argument("--nome", required=True, help="nome falado no início de cada episódio")
    ap.add_argument("--inicio", type=int, help="número do primeiro arquivo")
    ap.add_argument("--voz", default=VOZ_PADRAO)
    ap.add_argument("--velocidade", default="+0%", help="ex.: +10%%")
    ap.add_argument("--textos", default="textos", help="pasta para os roteiros .txt")
    ap.add_argument("--so-texto", action="store_true", help="não gera áudio")
    a = ap.parse_args()

    eps = dividir(ler_html(a.origem))
    if not eps:
        sys.exit("Nenhum TÍTULO/CAPÍTULO encontrado.")
    os.makedirs(a.textos, exist_ok=True)
    os.makedirs(PASTA_AUDIOS, exist_ok=True)
    num = a.inicio or proximo_numero()

    for i, ep in enumerate(eps):
        base = nome_arquivo(num + i, a.sigla, ep)
        texto = roteiro(ep, a.nome)
        with open(os.path.join(a.textos, base + ".txt"), "w", encoding="utf-8") as f:
            f.write(texto + "\n")
        mp3 = os.path.join(PASTA_AUDIOS, base + ".mp3")
        print(f"{base}  ({len(texto.split())} palavras)")
        if not a.so_texto and not os.path.exists(mp3):
            asyncio.run(falar(texto, mp3, a.voz, a.velocidade))
    print(f"\n{len(eps)} episódio(s).")


if __name__ == "__main__":
    main()
