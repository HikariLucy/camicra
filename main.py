from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
import os
import csv
import io
import base64
import pandas as pd
import requests
import google.generativeai as genai
from dotenv import load_dotenv
from collections import Counter
import jwt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Depends

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Configurar API Key de Gemini
if os.getenv("GEMINI_API_KEY"):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = FastAPI(title="CRA Backend API", description="API para el sistema de gestión del CRA", version="1.0.0")

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permitir todos los orígenes temporalmente
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "cra.db"

# --- Modelos Pydantic ---

class LibroCreate(BaseModel):
    titulo: str
    autor: str
    nivel: str
    tematicas: str
    estanteria: str
    isbn: Optional[str] = ""
    foto_blob: Optional[str] = None

class Libro(LibroCreate):
    id: int

class EventoCreate(BaseModel):
    nombre_evento: str
    fecha: str
    objetivo: Optional[str] = ""
    libros_seleccionados: Optional[str] = ""
    materiales: Optional[str] = ""
    resultados: Optional[str] = ""

class Evento(EventoCreate):
    id: int

class LoginRequest(BaseModel):
    username: str
    password: str

SECRET_KEY = "clave_secreta_super_segura_cra"
ALGORITHM = "HS256"
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Credenciales inválidas")
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

def inicializar_datos_demo():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM inventario")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO inventario (titulo, autor, nivel, tematicas, estanteria) VALUES (?, ?, ?, ?, ?)", [
            ("El Principito", "Antoine de Saint-Exupéry", "PRIMER CICLO", "Cuento, Infantil", "A1"),
            ("1984", "George Orwell", "TERCER CICLO", "Ficción, Distopía", "C2"),
            ("Cien años de soledad", "Gabriel García Márquez", "TERCER CICLO", "Novela, Realismo mágico", "C3"),
            ("Papelucho", "Marcela Paz", "SEGUNDO CICLO", "Infantil, Humor", "A2"),
            ("Don Quijote", "Miguel de Cervantes", "TERCER CICLO", "Clásico", "C1"),
            ("Harry Potter y la piedra filosofal", "J.K. Rowling", "SEGUNDO CICLO", "Fantasía, Juvenil", "B1"),
            ("El Hobbit", "J.R.R. Tolkien", "TERCER CICLO", "Fantasía, Épico", "B2"),
            ("Romeo y Julieta", "William Shakespeare", "TERCER CICLO", "Clásico, Romance", "C2"),
            ("La metamorfosis", "Franz Kafka", "TERCER CICLO", "Clásico, Existencialismo", "C1"),
            ("Subterra", "Baldomero Lillo", "TERCER CICLO", "Historia, Realismo", "D1"),
            ("El diario de Ana Frank", "Ana Frank", "TERCER CICLO", "Historia, Biografía", "D2"),
            ("Matilda", "Roald Dahl", "SEGUNDO CICLO", "Infantil, Fantasía", "A2"),
            ("Donde los monstruos viven", "Maurice Sendak", "Prekinder y Kinder NTP", "Cuento, Infantil", "A1"),
            ("Condorito", "Pepo", "PRIMER CICLO", "Cómic, Humor", "A3"),
            ("La ciudad y los perros", "Mario Vargas Llosa", "TERCER CICLO", "Novela, Ficción", "C3"),
            ("Mitos y leyendas de Chile", "Floridor Pérez", "SEGUNDO CICLO", "Mitología, Cuento", "D1"),
            ("Fahrenheit 451", "Ray Bradbury", "TERCER CICLO", "Ficción, Distopía", "C2"),
            ("El león, la bruja y el ropero", "C.S. Lewis", "SEGUNDO CICLO", "Fantasía, Aventura", "B1"),
            ("Macbeth", "William Shakespeare", "TERCER CICLO", "Clásico, Teatro", "C2"),
            ("Crónicas marcianas", "Ray Bradbury", "TERCER CICLO", "Ciencia Ficción", "B3"),
            ("Los juegos del hambre", "Suzanne Collins", "TERCER CICLO", "Ficción, Juvenil", "B1"),
            ("Cuentos de buenas noches para niñas rebeldes", "Elena Favilli", "SEGUNDO CICLO", "Biografía, Inspirador", "D3"),
            ("El monstruo de colores", "Anna Llenas", "Prekinder y Kinder NTP", "Cuento, Emociones", "A1"),
            ("Historia de una gaviota y del gato que le enseñó a volar", "Luis Sepúlveda", "PRIMER CICLO", "Fábula, Valores", "A2"),
            ("Veinte poemas de amor y una canción desesperada", "Pablo Neruda", "TERCER CICLO", "Poesía, Romance", "C4")
        ])
        
    cursor.execute("SELECT COUNT(*) FROM materiales")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO materiales (nombre, descripcion) VALUES (?, ?)", [
            ("Microscopio Escolar", "Microscopio de laboratorio básico con aumentos x100, x400."),
            ("Set de Regletas Cuisenaire", "Set de piezas de madera para comprensión matemática."),
            ("Mapa Físico Mundial", "Mapa mural grande con relieve y divisiones geográficas."),
            ("Set de Ajedrez", "Tablero y piezas para talleres extraescolares de desarrollo lógico."),
            ("Globo Terráqueo Político", "Globo con los países actualizados para la clase de historia.")
        ])
        
    cursor.execute("SELECT COUNT(*) FROM prestamos")
    if cursor.fetchone()[0] == 0:
        hoy = datetime.now()
        cursor.executemany("INSERT INTO prestamos (tipo_item, nombre_item, nombre_alumno, curso, fecha_prestamo, fecha_devolucion, estado) VALUES (?, ?, ?, ?, ?, ?, ?)", [
            ("Libro", "1984", "Juan Pérez", "I A", (hoy - timedelta(days=10)).strftime("%Y-%m-%d"), (hoy - timedelta(days=5)).strftime("%Y-%m-%d"), "Activo"),
            ("Material", "Microscopio Escolar", "Ana Gómez", "5 B", (hoy - timedelta(days=3)).strftime("%Y-%m-%d"), (hoy - timedelta(days=1)).strftime("%Y-%m-%d"), "Activo"),
            ("Libro", "El Principito", "Pedro Soto", "2", (hoy - timedelta(days=2)).strftime("%Y-%m-%d"), (hoy + timedelta(days=1)).strftime("%Y-%m-%d"), "Activo"),
            ("Libro", "Matilda", "Sofía López", "4 A", hoy.strftime("%Y-%m-%d"), (hoy + timedelta(days=3)).strftime("%Y-%m-%d"), "Activo"),
            ("Material", "Set de Ajedrez", "Carlos Ruiz", "6 A", hoy.strftime("%Y-%m-%d"), hoy.strftime("%Y-%m-%d"), "Activo"),
            ("Libro", "Condorito", "Marta Díaz", "3 B", hoy.strftime("%Y-%m-%d"), (hoy + timedelta(days=5)).strftime("%Y-%m-%d"), "Activo")
        ])
        
    conn.commit()
    conn.close()

# --- Rutas Auth ---
@app.post("/api/login")
def login(req: LoginRequest):
    if req.username == "camila" and req.password == "cra2026":
        pass
    elif req.username == "demo" and req.password == "demo":
        inicializar_datos_demo()
    else:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    
    expire = datetime.utcnow() + timedelta(hours=8)
    token = jwt.encode({"sub": req.username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)
    return {"token": token, "username": req.username}

class PrestamoCreate(BaseModel):
    tipo_item: str
    nombre_item: str
    nombre_alumno: str
    curso: str
    fecha_prestamo: str
    fecha_devolucion: str

class RecomendacionRequest(BaseModel):
    nombre_alumno: str
    libros_favoritos: List[str]

class GenerarEventoRequest(BaseModel):
    tipo_actividad: str
    objetivo: str

# --- Funciones de Base de Datos ---

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Permite acceder a las columnas por nombre
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Crear tabla de inventario
    cursor.execute('DROP TABLE IF EXISTS inventario')
    cursor.execute('''
        CREATE TABLE inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isbn TEXT,
            titulo TEXT NOT NULL,
            autor TEXT NOT NULL,
            nivel TEXT NOT NULL,
            tematicas TEXT NOT NULL,
            estanteria TEXT NOT NULL,
            foto_blob TEXT
        )
    ''')
    
    # Crear tabla de eventos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_evento TEXT NOT NULL,
            fecha TEXT NOT NULL,
            objetivo TEXT,
            libros_seleccionados TEXT,
            materiales TEXT,
            resultados TEXT
        )
    ''')
    
    # Crear tabla de materiales
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS materiales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            foto BLOB
        )
    ''')
    
    # Crear tabla de prestamos (con reconstrucción para asegurar el esquema nuevo)
    cursor.execute('DROP TABLE IF EXISTS prestamos')
    cursor.execute('''
        CREATE TABLE prestamos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_item TEXT NOT NULL,
            nombre_item TEXT NOT NULL,
            nombre_alumno TEXT NOT NULL,
            curso TEXT NOT NULL,
            fecha_prestamo TEXT NOT NULL,
            fecha_devolucion TEXT NOT NULL,
            estado TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

# Inicializar la base de datos al arrancar la aplicación
@app.on_event("startup")
def startup_event():
    init_db()

# --- Endpoints ---

@app.get("/api/inventario", response_model=List[Libro])
def get_inventario(current_user: str = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inventario")
    rows = cursor.fetchall()
    conn.close()
    
    libros = [dict(row) for row in rows]
    return libros

@app.get("/api/libros/buscar-isbn/{isbn}")
def buscar_isbn(isbn: str, current_user: str = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT titulo, autor, foto_blob FROM inventario WHERE isbn = ? LIMIT 1", (isbn,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {"titulo": row["titulo"], "autor": row["autor"], "foto_blob": row["foto_blob"], "origen": "local"}
        
    try:
        url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
        res = requests.get(url, timeout=5)
        data = res.json()
        book_key = f"ISBN:{isbn}"
        
        if book_key in data:
            book_data = data[book_key]
            titulo = book_data.get("title", "")
            autor = ", ".join([a.get("name", "") for a in book_data.get("authors", [])])
            
            foto_blob = None
            if "cover" in book_data and "medium" in book_data["cover"]:
                img_url = book_data["cover"]["medium"]
                img_res = requests.get(img_url, timeout=5)
                if img_res.status_code == 200:
                    foto_blob = base64.b64encode(img_res.content).decode("utf-8")
                    
            return {"titulo": titulo, "autor": autor, "foto_blob": foto_blob, "origen": "api"}
            
    except Exception as e:
        print("Error fetching from Open Library:", e)
        
    return {"titulo": "", "autor": "", "foto_blob": None, "origen": "not_found"}

@app.post("/api/inventario", response_model=Libro, status_code=201)
def create_libro(libro: LibroCreate, current_user: str = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO inventario (isbn, titulo, autor, nivel, tematicas, estanteria, foto_blob) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (libro.isbn, libro.titulo, libro.autor, libro.nivel, libro.tematicas, libro.estanteria, libro.foto_blob)
    )
    conn.commit()
    nuevo_id = cursor.lastrowid
    conn.close()
    
    return {**libro.dict(), "id": nuevo_id}

@app.get("/api/eventos", response_model=List[Evento])
def get_eventos(current_user: str = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM eventos")
    rows = cursor.fetchall()
    conn.close()
    
    eventos = [dict(row) for row in rows]
    return eventos

@app.post("/api/eventos", response_model=Evento, status_code=201)
def create_evento(evento: EventoCreate, current_user: str = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        INSERT INTO eventos 
        (nombre_evento, fecha, objetivo, libros_seleccionados, materiales, resultados) 
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (evento.nombre_evento, evento.fecha, evento.objetivo, 
         evento.libros_seleccionados, evento.materiales, evento.resultados)
    )
    conn.commit()
    nuevo_id = cursor.lastrowid
    conn.close()
    
    return {**evento.dict(), "id": nuevo_id}

@app.post("/api/inventario/importar")
async def importar_inventario(file: UploadFile = File(...), current_user: str = Depends(get_current_user)):
    if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Formato no soportado. Usa .csv, .xlsx o .xls")
        
    try:
        contents = await file.read()
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
            
        # Reemplazar NaN por cadenas vacías para SQLite
        df = df.fillna("")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        insertados = 0
        for index, row in df.iterrows():
            titulo = str(row.get("Título", ""))
            autor = str(row.get("Autor", ""))
            nivel = str(row.get("Nivel Recomendado", ""))
            tematicas = str(row.get("Temáticas", ""))
            estanteria = str(row.get("Estantería", "Sin Asignar"))
            
            if titulo:
                cursor.execute(
                    "INSERT INTO inventario (titulo, autor, nivel, tematicas, estanteria) VALUES (?, ?, ?, ?, ?)",
                    (titulo, autor, nivel, tematicas, estanteria)
                )
                insertados += 1
                
        conn.commit()
        conn.close()
        
        return {"mensaje": "Importación exitosa", "cantidad": insertados}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando archivo: {str(e)}")

# --- Endpoints Material Pedagógico ---

@app.post("/api/materiales")
async def crear_material(
    nombre: str = Form(...),
    descripcion: str = Form(...),
    foto: UploadFile = File(None),
    current_user: str = Depends(get_current_user)
):
    foto_blob = None
    if foto:
        foto_blob = await foto.read()
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO materiales (nombre, descripcion, foto) VALUES (?, ?, ?)",
        (nombre, descripcion, foto_blob)
    )
    conn.commit()
    nuevo_id = cursor.lastrowid
    conn.close()
    
    return {"mensaje": "Material creado exitosamente", "id": nuevo_id}

@app.get("/api/materiales")
def get_materiales(current_user: str = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, descripcion, foto FROM materiales")
    filas = cursor.fetchall()
    conn.close()
    
    materiales = []
    for fila in filas:
        mat = dict(fila)
        if mat["foto"]:
            # Convertir BLOB a Base64 para enviarlo al frontend
            base64_img = base64.b64encode(mat["foto"]).decode('utf-8')
            mat["foto"] = f"data:image/jpeg;base64,{base64_img}" # Asume jpeg, el browser usualmente auto-resuelve el mime si el magic header cuadra, o png. Para mayor robustez lo dejamos genérico.
        materiales.append(mat)
        
    return materiales

# --- Endpoints Préstamos ---

@app.post("/api/prestamos")
def crear_prestamo(prestamo: PrestamoCreate, current_user: str = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO prestamos (tipo_item, nombre_item, nombre_alumno, curso, fecha_prestamo, fecha_devolucion, estado)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (prestamo.tipo_item, prestamo.nombre_item, prestamo.nombre_alumno, prestamo.curso, prestamo.fecha_prestamo, prestamo.fecha_devolucion, "Activo")
    )
    conn.commit()
    nuevo_id = cursor.lastrowid
    conn.close()
    return {"mensaje": "Préstamo registrado", "id": nuevo_id}

@app.get("/api/prestamos/activos")
def get_prestamos_activos(current_user: str = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, i.estanteria 
        FROM prestamos p
        LEFT JOIN inventario i ON p.nombre_item = i.titulo AND p.tipo_item = 'Libro'
        WHERE p.estado = 'Activo' 
        ORDER BY p.fecha_devolucion ASC
    """)
    filas = cursor.fetchall()
    conn.close()
    return [dict(f) for f in filas]

@app.get("/api/prestamos/alerta-pendiente")
def check_alertas_pendientes(current_user: str = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    hoy = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT nombre_item, nombre_alumno, fecha_devolucion FROM prestamos WHERE estado = 'Activo' AND fecha_devolucion < ?", (hoy,))
    filas = cursor.fetchall()
    conn.close()
    detalles = [dict(f) for f in filas]
    return {"tiene_pendientes": len(detalles) > 0, "detalles": detalles}

@app.put("/api/prestamos/{prestamo_id}/devolver")
def devolver_prestamo(prestamo_id: int, current_user: str = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE prestamos SET estado = 'Devuelto' WHERE id = ?", (prestamo_id,))
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Préstamo no encontrado")
        
    conn.commit()
    conn.close()
    return {"mensaje": "Préstamo marcado como devuelto"}

# --- Endpoint Estadísticas ---
@app.get("/api/estadisticas")
def get_estadisticas(current_user: str = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Total de Libros
    cursor.execute("SELECT COUNT(*) FROM inventario")
    total_libros = cursor.fetchone()[0]
    
    # 2. Total de Materiales
    cursor.execute("SELECT COUNT(*) FROM materiales")
    total_materiales = cursor.fetchone()[0]
    
    # 3. Total de Préstamos Activos
    cursor.execute("SELECT COUNT(*) FROM prestamos WHERE estado = 'Activo'")
    prestamos_activos = cursor.fetchone()[0]
    
    # 4. Obtener temáticas y niveles
    cursor.execute("SELECT nivel, tematicas FROM inventario")
    filas = cursor.fetchall()
    conn.close()
    
    niveles = []
    tematicas_list = []
    
    for fila in filas:
        niveles.append(fila["nivel"])
        temas = [t.strip() for t in fila["tematicas"].split(",") if t.strip()]
        tematicas_list.extend(temas)
        
    contador_niveles = dict(Counter(niveles))
    contador_tematicas = dict(Counter(tematicas_list).most_common(5))
    
    return {
        "totales": {
            "libros": total_libros,
            "materiales": total_materiales,
            "prestamos_activos": prestamos_activos
        },
        "niveles": contador_niveles,
        "tematicas": contador_tematicas
    }

@app.post("/api/recomendacion-ia")
def generar_recomendacion_ia(req: RecomendacionRequest, current_user: str = Depends(get_current_user)):
    if not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="API Key de Gemini no configurada en las variables de entorno.")
        
    # Obtener el catálogo actual para dárselo de contexto a la IA
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT titulo, autor FROM inventario")
    libros = cursor.fetchall()
    conn.close()
    
    catalogo_texto = ", ".join([f"'{row['titulo']}' por {row['autor']}" for row in libros])
    if not catalogo_texto:
        catalogo_texto = "El catálogo está vacío actualmente."
        
    libros_fav_str = ", ".join(req.libros_favoritos)
    
    prompt_rec = f"""
    Eres experto en bibliotecas escolares. El alumno {req.nombre_alumno} disfrutó de los siguientes libros: '{libros_fav_str}'.
    Catálogo disponible en la biblioteca: {catalogo_texto}.
    
    Responde con la siguiente estructura exacta:
    
    ### 📖 Perfil Lector: {req.nombre_alumno}
    
    **📚 Recomendaciones para el alumno:**
    1. (Sugiere 3 libros del catálogo, sin repetir sus libros favoritos y acordes a sus gustos).
    2. Brevemente explica por qué le gustarán.
    3. Sugiere una pregunta mágica para despertar su curiosidad.
    
    ---
    
    **🏆 DIPLOMA PARA IMPRIMIR:**
    (Diseña un mini diploma hermoso usando Markdown. Usa emojis llamativos, blockquotes (el signo >), texto en negrita y cursiva para que parezca un certificado real de fomento lector. Debe ser corto, mágico y dirigido a {req.nombre_alumno}).
    """
    
    try:
        # Cambiado a gemini-2.5-flash para evitar los límites de cuota (Rate Limits)
        modelo = genai.GenerativeModel("gemini-2.5-flash")
        respuesta = modelo.generate_content(prompt_rec)
        return {"respuesta": respuesta.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar recomendación: {str(e)}")

@app.post("/api/generar-evento-ia")
def generar_evento_ia(req: GenerarEventoRequest, current_user: str = Depends(get_current_user)):
    if not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="API Key de Gemini no configurada.")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT titulo, autor, nivel FROM inventario")
    libros = cursor.fetchall()
    conn.close()
    
    catalogo_texto = ", ".join([f"'{row['titulo']}' por {row['autor']} ({row['nivel']})" for row in libros])
    if not catalogo_texto:
        catalogo_texto = "El catálogo está vacío actualmente."
        
    prompt_evento = f"""
    Eres un bibliotecario escolar experto. Ayúdame a planificar un evento de {req.tipo_actividad} para el CRA. 
    Objetivo del evento: {req.objetivo}
    
    Basándote en el inventario actual de la biblioteca: {catalogo_texto}
    
    Sugiere:
    1. Un título creativo para el evento.
    2. Descripción y público objetivo.
    3. Lista de materiales necesarios.
    4. Qué libros podríamos exhibir o usar del catálogo.
    5. Qué actividades lúdicas realizar para incentivar la lectura.
    
    Formatea la respuesta usando Markdown para que sea fácil de leer.
    """
    
    try:
        modelo = genai.GenerativeModel("gemini-2.5-flash")
        respuesta = modelo.generate_content(prompt_evento)
        return {"respuesta": respuesta.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar evento: {str(e)}")

@app.post("/api/migrar-csv")
def migrar_csv(current_user: str = Depends(get_current_user)):
    # Rutas a los archivos originales (ajusta si los moviste de carpeta)
    ruta_inventario = r"..\cami CRA\inventario_libros.csv"
    ruta_eventos = r"..\cami CRA\eventos_cra.csv"
    
    resultados = {"inventario_insertados": 0, "eventos_insertados": 0, "errores": []}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Migrar Inventario
    try:
        if os.path.exists(ruta_inventario):
            with open(ruta_inventario, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cursor.execute(
                        "INSERT INTO inventario (titulo, autor, nivel, tematicas) VALUES (?, ?, ?, ?)",
                        (row.get("Título", ""), row.get("Autor", ""), row.get("Nivel Recomendado", ""), row.get("Temáticas", ""))
                    )
                    resultados["inventario_insertados"] += 1
        else:
            resultados["errores"].append("inventario_libros.csv no encontrado.")
    except Exception as e:
        resultados["errores"].append(f"Error migrando inventario: {str(e)}")

    # Migrar Eventos
    try:
        if os.path.exists(ruta_eventos):
            with open(ruta_eventos, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cursor.execute(
                        "INSERT INTO eventos (nombre_evento, fecha, objetivo, libros_seleccionados, materiales, resultados) VALUES (?, ?, ?, ?, ?, ?)",
                        (row.get("Nombre Evento", ""), row.get("Fecha", ""), row.get("Objetivo", ""), row.get("Libros Seleccionados", ""), "", "")
                    )
                    resultados["eventos_insertados"] += 1
        else:
            resultados["errores"].append("eventos_cra.csv no encontrado.")
    except Exception as e:
        resultados["errores"].append(f"Error migrando eventos: {str(e)}")

    conn.commit()
    conn.close()
    
    return {"mensaje": "Migración finalizada", "detalles": resultados}

# --- Montar Frontend ---
# Esto sirve el archivo index.html cuando visitas la raíz de la web
@app.get("/")
def read_root():
    ruta_index = os.path.join("frontend", "index.html")
    if os.path.exists(ruta_index):
        return FileResponse(ruta_index)
    return {"mensaje": "Frontend no encontrado. Asegúrate de que la carpeta 'frontend' existe."}

# Esto monta la carpeta completa para servir app.js, css, imágenes, etc.
app.mount("/", StaticFiles(directory="frontend"), name="frontend")


