# vim: set ft=rst:

See https://help.pythonanywhere.com/ (or click the "Help" link at the top
right) for help on how to use PythonAnywhere, including tips on copying and
pasting from consoles, and writing your own web applications.

# Clonar el repositorio
git clone https://github.com/padeldondesea/registro-convocatoria.git
cd registro-convocatoria

# Crear un entorno virtual (recomendado)
python3 -m venv venv

# Activar el entorno virtual
# En Linux/macOS:
source venv/bin/activate
# En Windows:
venv\Scripts\activate

# Instalar las dependencias
pip install -r requirements.txt

# Ejecutar la aplicación
python app.py
