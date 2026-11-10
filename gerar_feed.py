#!/usr/bin/env python3
"""
Gera um feed RSS (feed.xml) de podcast a partir dos MP3 de uma pasta,
para seguir no Apple Podcasts via "Seguir um programa por URL".

Uso:
    python3 gerar_feed.py

Antes de rodar, ajuste as CONFIGURAÇÕES abaixo.
Os episódios seguem a ordem alfabética dos nomes dos arquivos,
então nomeie assim: 001 - CF Art 1 a 4.mp3, 002 - CF Art 5.mp3, ...
"""

import os
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from urllib.parse import quote
from xml.sax.saxutils import escape

# ===================== CONFIGURAÇÕES =====================
URL_BASE = "https://vitorantonioas.github.io/legislacao-audio"  # sem barra no final
PASTA_AUDIOS = "audios"           # pasta (dentro do repositório) com os MP3
TITULO = "Legislação em Áudio"
DESCRICAO = "Meu podcast particular de legislação."
AUTOR = "Vitor"
IMAGEM = ""                      # opcional: imagem quadrada (1400x1400 a 3000x3000). Deixe "" se não tiver.
# =========================================================


def main():
    arquivos = sorted(f for f in os.listdir(PASTA_AUDIOS) if f.lower().endswith(".mp3"))
    if not arquivos:
        print(f"Nenhum MP3 encontrado em '{PASTA_AUDIOS}'.")
        return

    # Datas sequenciais para o app manter a ordem dos arquivos
    inicio = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    itens = []
    for i, nome in enumerate(arquivos, start=1):
        caminho = os.path.join(PASTA_AUDIOS, nome)
        tamanho = os.path.getsize(caminho)
        url = f"{URL_BASE}/{quote(PASTA_AUDIOS)}/{quote(nome)}"
        titulo_ep = os.path.splitext(nome)[0]
        data = format_datetime(inicio + timedelta(hours=i))
        itens.append(f"""    <item>
      <title>{escape(titulo_ep)}</title>
      <enclosure url="{escape(url)}" length="{tamanho}" type="audio/mpeg"/>
      <guid isPermaLink="false">{escape(nome)}</guid>
      <pubDate>{data}</pubDate>
      <itunes:episode>{i}</itunes:episode>
    </item>""")

    imagem_xml = ""
    if IMAGEM:
        imagem_xml = f'    <itunes:image href="{escape(URL_BASE + "/" + quote(IMAGEM))}"/>\n'

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{escape(TITULO)}</title>
    <link>{escape(URL_BASE)}</link>
    <description>{escape(DESCRICAO)}</description>
    <language>pt-br</language>
    <itunes:author>{escape(AUTOR)}</itunes:author>
    <itunes:type>serial</itunes:type>
    <itunes:block>Yes</itunes:block>
{imagem_xml}{chr(10).join(itens)}
  </channel>
</rss>
"""
    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write(feed)
    print(f"feed.xml gerado com {len(itens)} episódio(s).")
    print(f"URL para o Apple Podcasts: {URL_BASE}/feed.xml")


if __name__ == "__main__":
    main()
