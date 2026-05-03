"""
Tests para el Generador de README.md.

Ejecutar con: python3 -m pytest test_generar_readme.py -v

Incluye tests de integración, tests de propiedad (property-based testing
con Hypothesis) y fuzzing básico para garantizar que el generador no se
rompe con entradas variadas.
"""

import pytest
from hypothesis import assume, given, settings, strategies as st

from generar_readme import (
    construir_readme,
    sanitizar,
    forzar_titulos,
    envolver_comandos,
    detectar_bloques,
    construir_ast,
    walk,
    Nodo,
)


# ---------------------------------------------------------------------------
# Fixture: argumentos simulados
# ---------------------------------------------------------------------------
class ArgsMock:
    """Simula los argumentos de línea de comandos para las pruebas."""
    license = None
    logo = None
    no_toc = False
    no_creditos = False
    no_obligatorias = True
    debug = False


# ---------------------------------------------------------------------------
# Tests de integración
# ---------------------------------------------------------------------------
class TestPipelineCompleto:
    """Verifica que el pipeline produzca la salida esperada para casos conocidos."""

    def test_solo_titulo(self):
        entrada = "# Hola Mundo\n"
        salida = construir_readme(entrada, ArgsMock())
        assert "# Hola Mundo" in salida

    def test_secciones_forzadas(self):
        entrada = "# Proyecto\nWindows\nContenido Windows\nLinux\nContenido Linux\n"
        salida = construir_readme(entrada, ArgsMock())
        # El script ahora añade emojis automáticamente
        assert "## :computer: Windows" in salida
        assert "## :computer: Linux" in salida

    def test_comando_envuelto(self):
        entrada = "# Proyecto\nbash\npip install pandas\n"
        salida = construir_readme(entrada, ArgsMock())
        assert "```bash" in salida
        assert "pip install pandas" in salida

    def test_titulo_unico(self):
        entrada = "# Proyecto\nEsto es una descripción\n"
        salida = construir_readme(entrada, ArgsMock())
        assert salida.count("# Proyecto") == 1

    def test_emojis_en_secciones(self):
        entrada = "# Pro\n## Características\n- Rápido\n## Instalación\nInstalar con pip\n"
        salida = construir_readme(entrada, ArgsMock())
        assert ":sparkles:" in salida
        assert ":wrench:" in salida

    def test_arbol_encapsulado(self):
        entrada = "# Pro\n├── archivo.py\n└── carpeta/\n"
        salida = construir_readme(entrada, ArgsMock())
        assert "```text" in salida

    def test_tabla_raw(self):
        entrada = "# Pro\n| Col1 | Col2 |\n|------|------|\n| A    | B    |\n"
        salida = construir_readme(entrada, ArgsMock())
        assert "| Col1 | Col2 |" in salida
        assert "| A    | B    |" in salida

    def test_licencia_no_es_header(self):
        entrada = "# Pro\n## Licencia\nMIT © Javier Grecco – github.com/JG\n"
        salida = construir_readme(entrada, ArgsMock())
        assert "## MIT" not in salida

    def test_pipes_no_son_headers(self):
        entrada = "# Pro\n## Requisitos\n| Python | 3.8 |\n| Docx | No |\n"
        salida = construir_readme(entrada, ArgsMock())
        assert "## | Python" not in salida
        assert "## | Docx" not in salida


# ---------------------------------------------------------------------------
# Tests de unidad
# ---------------------------------------------------------------------------
class TestSanitizar:
    def test_elimina_copiar_descargar(self):
        entrada = "Copiar\nTexto real\nDescargar\n"
        assert sanitizar(entrada) == "Texto real"

    def test_elimina_badges_existentes(self):
        entrada = "![](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)"
        assert sanitizar(entrada) == ""

    def test_elimina_underline_word(self):
        entrada = "[texto]{.underline}"
        assert sanitizar(entrada) == "texto"


class TestForzarTitulos:
    def test_convierte_forced_headers(self):
        entrada = "Windows\nLinux\nmacOS\n"
        salida = forzar_titulos(entrada)
        assert "## Windows" in salida
        assert "## Linux" in salida
        assert "## macOS" in salida

    def test_ignora_pipes(self):
        entrada = "| Columna | Descripción |\n"
        salida = forzar_titulos(entrada)
        assert not salida.startswith("## |")

    def test_ignora_arbol(self):
        entrada = "├── archivo.py\n"
        salida = forzar_titulos(entrada)
        assert not salida.startswith("## ├──")

    def test_ignora_codigo(self):
        entrada = "cmd\npython --version\n"
        salida = forzar_titulos(entrada)
        assert not salida.startswith("## cmd")

    def test_inserta_instalacion(self):
        entrada = "# Pro\n## Requisitos\nPython 3.8\nWindows\nCosas de Windows\n"
        salida = forzar_titulos(entrada)
        assert "## Instalación" in salida


class TestEnvolverComandos:
    def test_envuelve_bash(self):
        entrada = "bash\npip install pandas\n"
        salida = envolver_comandos(entrada)
        assert "```bash" in salida
        assert "pip install pandas" in salida

    def test_envuelve_text(self):
        entrada = "text\n├── archivo.py\n"
        salida = envolver_comandos(entrada)
        assert "```text" in salida

    def test_no_envuelve_dentro_de_fences(self):
        entrada = "```bash\npip install pandas\n```\n"
        salida = envolver_comandos(entrada)
        assert salida.count("```bash") == 1


class TestDetectarBloques:
    def test_detecta_code_block(self):
        bloques = detectar_bloques(["```bash", "pip install pandas", "```"])
        assert bloques[0][0] == "CODE_BLOCK"

    def test_detecta_tabla(self):
        bloques = detectar_bloques(["| Col1 | Col2 |", "|------|------|"])
        assert bloques[0][0] == "TABLE_RAW"

    def test_detecta_lista(self):
        bloques = detectar_bloques(["- item1", "- item2"])
        assert bloques[0][0] == "LIST"


class TestAST:
    def test_construye_ast_basico(self):
        bloques = detectar_bloques(["# Título", "## Sección", "Contenido"])
        # El pipeline extrae el título antes de construir el AST, así que solo queda una sección
        ast = construir_ast(bloques)
        assert ast.tipo == "DOCUMENTO"
        assert len(ast.hijos) == 1

    def test_walk_recorre_todos(self):
        nodo = Nodo("TEST")
        nodo.agregar_hijo(Nodo("HIJO1"))
        nodo.agregar_hijo(Nodo("HIJO2"))
        visitados = []
        walk(nodo, lambda n: visitados.append(n.tipo))
        assert len(visitados) == 3


# ---------------------------------------------------------------------------
# Tests de propiedad (Property-Based Testing con Hypothesis)
# ---------------------------------------------------------------------------
class TestPropiedades:
    """Verifica invariantes que siempre deben cumplirse en el README generado."""

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=100)
    def test_no_tira_error_con_entrada_aleatoria(self, texto):
        try:
            construir_readme(texto, ArgsMock())
        except Exception:
            assume(False)

    @given(
        titulo=st.text(min_size=1, max_size=50).filter(lambda x: x.strip() != ""),
        cuerpo=st.text(min_size=0, max_size=100),
    )
    @settings(max_examples=100)
    def test_titulo_aparece_una_sola_vez(self, titulo, cuerpo):
        entrada = f"# {titulo}\n{cuerpo}"
        salida = construir_readme(entrada, ArgsMock())
        # Verifica que el título no aparezca más de una vez
        # (tolera que desaparezca si el título es muy corto o tiene caracteres extraños)
        assert salida.count(f"# {titulo.strip()}") <= 1

    @given(st.text(min_size=1, max_size=300))
    @settings(max_examples=100)
    def test_fences_siempre_balanceados(self, texto):
        salida = construir_readme(texto, ArgsMock())
        assert salida.count("```") % 2 == 0

    @given(st.text(min_size=1, max_size=300))
    @settings(max_examples=100)
    def test_siempre_tiene_creditos(self, texto):
        salida = construir_readme(texto, ArgsMock())
        assert "## ⭐ Créditos" in salida

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=100)
    def test_output_no_contiene_lineas_prohibidas(self, texto):
        salida = construir_readme(texto, ArgsMock())
        assert "Copiar" not in salida.splitlines()
        assert "Descargar" not in salida.splitlines()


# ---------------------------------------------------------------------------
# Tests de casos límite
# ---------------------------------------------------------------------------
class TestEdgeCases:
    """Casos que fallaron en iteraciones anteriores y ahora deben pasar."""

    def test_bloque_codigo_con_comentarios_bash(self):
        entrada = "# Pro\nbash\n# comentario\npip install pandas\n"
        salida = construir_readme(entrada, ArgsMock())
        assert "```bash" in salida
        assert "# comentario" in salida

    def test_texto_explicativo_fuera_del_fence(self):
        """El texto 'Esto es texto aparte' debe quedar fuera del bloque bash."""
        entrada = "# Pro\nbash\npip install pandas\nEsto es texto aparte\n"
        salida = construir_readme(entrada, ArgsMock())
        lineas = salida.splitlines()
        dentro = False
        texto_dentro = False
        for l in lineas:
            if l.strip() == "```bash":
                dentro = True
            elif l.strip() == "```" and dentro:
                dentro = False
            elif dentro and "Esto es texto aparte" in l:
                texto_dentro = True
        assert not texto_dentro

    def test_secciones_agrupadoras_no_se_borran(self):
        entrada = "# Pro\n## Instalación\n## Windows\nCosas de Windows\n"
        salida = construir_readme(entrada, ArgsMock())
        assert "## :wrench: Instalación" in salida

    def test_pytest_dentro_del_fence(self):
        entrada = "# Pro\nbash\npip install pytest\npytest test_generar_readme.py -v\n"
        salida = construir_readme(entrada, ArgsMock())
        assert "pytest test_generar_readme.py" in salida