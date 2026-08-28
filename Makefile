.PHONY: html pdf epub slides toc all clean

all: html pdf epub

html: ## 整书 HTML (pandoc)
	python3 build/compile.py html

pdf: ## PDF (xelatex + ctex + biber)
	python3 build/compile.py pdf

epub: ## EPUB3 (pandoc)
	python3 build/compile.py epub

slides: ## 从 src/slides/*.md 渲染 slide HTML (需 API)
	python3 build/compile.py slides

toc: ## 列出所有章节/幻灯片状态
	python3 build/compile.py toc

clean: ## 清除 output/
	rm -rf output/ static/slides_decks
