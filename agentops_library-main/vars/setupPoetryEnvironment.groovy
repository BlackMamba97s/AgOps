def call(def appRepo){
    sh '''
        set -e


        echo "Leggo la versione di Python richiesta..."
        PYTHON_VERSION=$(grep -E '^\\s*requires-python\\s*=' pyproject.toml | sed -E 's/.*">=([0-9]+\\.[0-9]+).*/\\1/')
        echo "Versione Python richiesta: $PYTHON_VERSION"

        echo "Verifico se Python $PYTHON_VERSION è installato via pyenv..."
        if ! pyenv versions --bare | grep -qx "$PYTHON_VERSION"; then
            echo "Installo Python $PYTHON_VERSION"
            pyenv install "$PYTHON_VERSION"
            export POETRY_VIRTUALENVS_CREATE=true
            poetry env use $(pyenv which python)
        else
            echo "Python $PYTHON_VERSION già installato"
        fi

        

        echo "Attivo pyenv con la versione desiderata"
        export PYENV_ROOT="$HOME/.pyenv"
        export PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"
        eval "$(pyenv init -)"

        pyenv shell "$PYTHON_VERSION"
        python --version  # per verifica

        echo "Installo le dipendenze (usando pip o poetry, se disponibile)"
        if command -v poetry >/dev/null 2>&1; then
            poetry install
        else
            pip install -r requirements.txt || echo "No requirements.txt trovato"
        fi
    '''

}