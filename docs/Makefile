all: operators.png parens.png semiclean

graphics.pdf: graphics.tex
	pdflatex $<

graphics-0.png graphics-1.png: graphics.pdf
	convert -density 800 $< -alpha off -resize 25% graphics.png

operators.png: graphics-0.png
	mv graphics-0.png operators.png

parens.png: graphics-1.png
	mv graphics-1.png parens.png

semiclean:
	rm -f graphics.pdf graphics.aux graphics.log

clean: semiclean
	rm -f operators.png parens.png

.PHONY: all semiclean clean
