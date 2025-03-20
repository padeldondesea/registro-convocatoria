import sqlite3

def init_db():
    conn = sqlite3.connect('/home/sstenta/convocatoria.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS registrados (nombre TEXT PRIMARY KEY)''')
    c.execute('''CREATE TABLE IF NOT EXISTS lista_espera (nombre TEXT PRIMARY KEY)''')
    conn.commit()
    conn.close()
    print("Base de datos inicializada correctamente.")

if __name__ == "__main__":
    init_db()