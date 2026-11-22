#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p tmp/pdfs output/pdf
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=tmp/pdfs docs/informe_unidad2.tex
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=tmp/pdfs docs/informe_unidad2.tex
cp tmp/pdfs/informe_unidad2.pdf output/pdf/Informe_Unidad_2_Algoritmos_Heuristicos.pdf
