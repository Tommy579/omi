# Makefile pour OMI (Open Mind Interface)

.PHONY: install run test build-release clean

# Détection de l'OS
ifeq ($(OS),Windows_NT)
    VENV_BIN = .venv\Scripts
    PYTHON = $(VENV_BIN)\python.exe
    PIP = $(VENV_BIN)\pip.exe
    RM = rmdir /s /q
else
    VENV_BIN = .venv/bin
    PYTHON = $(VENV_BIN)/python
    PIP = $(VENV_BIN)/pip
    RM = rm -rf
endif

install:
	@echo "Création de l'environnement virtuel (.venv)..."
	python3 -m venv .venv || python -m venv .venv
	@echo "Installation des dépendances depuis requirements.txt..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "Installation terminée avec succès."

run:
	@echo "Démarrage de l'assistant OMI..."
	$(PYTHON) main.py

test:
	@echo "Lancement des tests unitaires..."
	$(PYTHON) -m unittest discover -s tests

build-release:
	@echo "Lancement de la compilation de release..."
	$(PYTHON) build_release.py

clean:
	@echo "Nettoyage des dossiers de build..."
	$(RM) build dist
