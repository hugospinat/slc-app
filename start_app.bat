@echo off
echo Démarrage de l'application de contrôle des charges...
echo.
echo Activation de l'environnement virtuel...
call .venv\Scripts\activate.bat
echo.
echo Lancement de Streamlit...
echo L'application sera disponible à l'adresse: http://localhost:8501
echo.
streamlit run app.py
pause
