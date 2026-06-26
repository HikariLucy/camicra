from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import csv
import io
import base64
import pandas as pd
import requests
import google.generativeai as genai
from dotenv import load_dotenv
import json
from collections import Counter
import jwt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta

# SQLAlchemy Imports
# pyrefly: ignore [missing-import]
from sqlalchemy import create_engine, Column, Integer, String, Text, LargeBinary
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import sessionmaker, declarative_base, Session

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

# --- Configuración de Base de Datos (SQLAlchemy) ---
# Usar DATABASE_URL de entorno, o caer en SQLite si no está definido
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cra.db")
# SQLAlchemy requiere 'postgresql://' en lugar de 'postgres://' (que es el antiguo estilo que a veces dan los proveedores)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Argumentos de conexión, necesarios para SQLite en hilos de FastAPI
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Modelos SQLAlchemy (ORM) ---

class InventarioDB(Base):
    __tablename__ = "inventario"
    id = Column(Integer, primary_key=True, index=True)
    isbn = Column(String, nullable=True)
    titulo = Column(String, nullable=False)
    autor = Column(String, nullable=False)
    nivel = Column(String, nullable=False)
    tematicas = Column(String, nullable=False)
    estanteria = Column(String, nullable=False, default="Sin Asignar")
    foto_blob = Column(Text, nullable=True)

class EventoDB(Base):
    __tablename__ = "eventos"
    id = Column(Integer, primary_key=True, index=True)
    nombre_evento = Column(String, nullable=False)
    fecha = Column(String, nullable=False)
    objetivo = Column(String, nullable=True)
    libros_seleccionados = Column(String, nullable=True)
    materiales = Column(String, nullable=True)
    resultados = Column(String, nullable=True)

class MaterialDB(Base):
    __tablename__ = "materiales"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    descripcion = Column(String, nullable=True)
    foto = Column(LargeBinary, nullable=True)

class PrestamoDB(Base):
    __tablename__ = "prestamos"
    id = Column(Integer, primary_key=True, index=True)
    tipo_item = Column(String, nullable=False)
    nombre_item = Column(String, nullable=False)
    nombre_alumno = Column(String, nullable=False)
    curso = Column(String, nullable=False)
    fecha_prestamo = Column(String, nullable=False)
    fecha_devolucion = Column(String, nullable=False)
    estado = Column(String, nullable=False, default="Activo")

# Inicializar la base de datos al arrancar la aplicación
@app.on_event("startup")
def startup_event():
    # Crea las tablas si no existen
    Base.metadata.create_all(bind=engine)


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
    class Config:
        orm_mode = True

class EventoCreate(BaseModel):
    nombre_evento: str
    fecha: str
    objetivo: Optional[str] = ""
    libros_seleccionados: Optional[str] = ""
    materiales: Optional[str] = ""
    resultados: Optional[str] = ""

class Evento(EventoCreate):
    id: int
    class Config:
        orm_mode = True

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

def inicializar_datos_demo(db: Session):
    if db.query(InventarioDB).count() == 0:
        demo_libros = [
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
        ]
        for titulo, autor, nivel, tematicas, estanteria in demo_libros:
            db.add(InventarioDB(titulo=titulo, autor=autor, nivel=nivel, tematicas=tematicas, estanteria=estanteria))
        
    if db.query(MaterialDB).count() == 0:
        demo_materiales = [
            ("Microscopio Escolar", "Microscopio de laboratorio básico con aumentos x100, x400."),
            ("Set de Regletas Cuisenaire", "Set de piezas de madera para comprensión matemática."),
            ("Mapa Físico Mundial", "Mapa mural grande con relieve y divisiones geográficas."),
            ("Set de Ajedrez", "Tablero y piezas para talleres extraescolares de desarrollo lógico."),
            ("Globo Terráqueo Político", "Globo con los países actualizados para la clase de historia.")
        ]
        for nombre, descripcion in demo_materiales:
            db.add(MaterialDB(nombre=nombre, descripcion=descripcion))
        
    if db.query(PrestamoDB).count() == 0:
        hoy = datetime.now()
        demo_prestamos = [
            ("Libro", "1984", "Juan Pérez", "I A", (hoy - timedelta(days=10)).strftime("%Y-%m-%d"), (hoy - timedelta(days=5)).strftime("%Y-%m-%d"), "Activo"),
            ("Material", "Microscopio Escolar", "Ana Gómez", "5 B", (hoy - timedelta(days=3)).strftime("%Y-%m-%d"), (hoy - timedelta(days=1)).strftime("%Y-%m-%d"), "Activo"),
            ("Libro", "El Principito", "Pedro Soto", "2", (hoy - timedelta(days=2)).strftime("%Y-%m-%d"), (hoy + timedelta(days=1)).strftime("%Y-%m-%d"), "Activo"),
            ("Libro", "Matilda", "Sofía López", "4 A", hoy.strftime("%Y-%m-%d"), (hoy + timedelta(days=3)).strftime("%Y-%m-%d"), "Activo"),
            ("Material", "Set de Ajedrez", "Carlos Ruiz", "6 A", hoy.strftime("%Y-%m-%d"), hoy.strftime("%Y-%m-%d"), "Activo"),
            ("Libro", "Condorito", "Marta Díaz", "3 B", hoy.strftime("%Y-%m-%d"), (hoy + timedelta(days=5)).strftime("%Y-%m-%d"), "Activo")
        ]
        for tipo, nombre, alumno, curso, f_prest, f_dev, estado in demo_prestamos:
            db.add(PrestamoDB(tipo_item=tipo, nombre_item=nombre, nombre_alumno=alumno, curso=curso, fecha_prestamo=f_prest, fecha_devolucion=f_dev, estado=estado))
            
    db.commit()

# --- Rutas Auth ---
@app.post("/api/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    if req.username == "camila" and req.password == "cra2026":
        pass
    elif req.username == "demo" and req.password == "demo":
        inicializar_datos_demo(db)
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

# --- Endpoints Inventario ---

@app.get("/api/inventario")
def get_inventario(current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    libros = db.query(InventarioDB).all()
    # FastAPI Serializará automáticamente los modelos SQLAlchemy si se configuran bien, 
    # pero para mayor robustez devolvemos una lista de diccionarios
    return [
        {
            "id": l.id, "isbn": l.isbn, "titulo": l.titulo, "autor": l.autor,
            "nivel": l.nivel, "tematicas": l.tematicas, "estanteria": l.estanteria,
            "foto_blob": l.foto_blob
        } 
        for l in libros
    ]

@app.get("/api/libros/buscar-isbn/{isbn}")
def buscar_isbn(isbn: str, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    libro_db = db.query(InventarioDB).filter(InventarioDB.isbn == isbn).first()
    
    if libro_db:
        return {"titulo": libro_db.titulo, "autor": libro_db.autor, "foto_blob": libro_db.foto_blob, "origen": "local"}
        
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

@app.post("/api/inventario", status_code=201)
def create_libro(libro: LibroCreate, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    nuevo_libro = InventarioDB(
        isbn=libro.isbn,
        titulo=libro.titulo,
        autor=libro.autor,
        nivel=libro.nivel,
        tematicas=libro.tematicas,
        estanteria=libro.estanteria,
        foto_blob=libro.foto_blob
    )
    db.add(nuevo_libro)
    db.commit()
    db.refresh(nuevo_libro)
    
    return {**libro.dict(), "id": nuevo_libro.id}

@app.get("/api/eventos")
def get_eventos(current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    eventos = db.query(EventoDB).all()
    return [
        {
            "id": e.id, "nombre_evento": e.nombre_evento, "fecha": e.fecha,
            "objetivo": e.objetivo, "libros_seleccionados": e.libros_seleccionados,
            "materiales": e.materiales, "resultados": e.resultados
        }
        for e in eventos
    ]

@app.post("/api/eventos", status_code=201)
def create_evento(evento: EventoCreate, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    nuevo_evento = EventoDB(
        nombre_evento=evento.nombre_evento,
        fecha=evento.fecha,
        objetivo=evento.objetivo,
        libros_seleccionados=evento.libros_seleccionados,
        materiales=evento.materiales,
        resultados=evento.resultados
    )
    db.add(nuevo_evento)
    db.commit()
    db.refresh(nuevo_evento)
    
    return {**evento.dict(), "id": nuevo_evento.id}

@app.post("/api/inventario/importar")
async def importar_inventario(file: UploadFile = File(...), current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Formato no soportado. Usa .csv, .xlsx o .xls")
        
    try:
        contents = await file.read()
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
            
        # Reemplazar NaN por cadenas vacías para SQLite/Postgres
        df = df.fillna("")
        
        insertados = 0
        for index, row in df.iterrows():
            titulo = str(row.get("Título", ""))
            autor = str(row.get("Autor", ""))
            nivel = str(row.get("Nivel Recomendado", ""))
            tematicas = str(row.get("Temáticas", ""))
            estanteria = str(row.get("Estantería", "Sin Asignar"))
            
            if titulo:
                nuevo_libro = InventarioDB(
                    titulo=titulo, autor=autor, nivel=nivel, 
                    tematicas=tematicas, estanteria=estanteria
                )
                db.add(nuevo_libro)
                insertados += 1
                
        db.commit()
        
        return {"mensaje": "Importación exitosa", "cantidad": insertados}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error procesando archivo: {str(e)}")

# --- Endpoints Material Pedagógico ---

@app.post("/api/materiales")
async def crear_material(
    nombre: str = Form(...),
    descripcion: str = Form(...),
    foto: UploadFile = File(None),
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    foto_blob = None
    if foto:
        foto_blob = await foto.read()
        
    nuevo_material = MaterialDB(nombre=nombre, descripcion=descripcion, foto=foto_blob)
    db.add(nuevo_material)
    db.commit()
    db.refresh(nuevo_material)
    
    return {"mensaje": "Material creado exitosamente", "id": nuevo_material.id}

@app.get("/api/materiales")
def get_materiales(current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    materiales_db = db.query(MaterialDB).all()
    
    materiales_list = []
    for mat in materiales_db:
        mat_dict = {"id": mat.id, "nombre": mat.nombre, "descripcion": mat.descripcion, "foto": None}
        if mat.foto:
            # Convertir BLOB a Base64 para enviarlo al frontend
            base64_img = base64.b64encode(mat.foto).decode('utf-8')
            mat_dict["foto"] = f"data:image/jpeg;base64,{base64_img}"
        materiales_list.append(mat_dict)
        
    return materiales_list

# --- Endpoints Préstamos ---

@app.post("/api/prestamos")
def crear_prestamo(prestamo: PrestamoCreate, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    nuevo_prestamo = PrestamoDB(
        tipo_item=prestamo.tipo_item,
        nombre_item=prestamo.nombre_item,
        nombre_alumno=prestamo.nombre_alumno,
        curso=prestamo.curso,
        fecha_prestamo=prestamo.fecha_prestamo,
        fecha_devolucion=prestamo.fecha_devolucion,
        estado="Activo"
    )
    db.add(nuevo_prestamo)
    db.commit()
    db.refresh(nuevo_prestamo)
    return {"mensaje": "Préstamo registrado", "id": nuevo_prestamo.id}

@app.get("/api/prestamos/activos")
def get_prestamos_activos(current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    # Reemplazo de LEFT JOIN: Obtener préstamos y estantería manual o usando la sesión (forma más limpia en ORM)
    # pyrefly: ignore [missing-import]
    from sqlalchemy.orm import aliased
    
    # Esta consulta usa join para replicar la lógica anterior
    prestamos_con_estanteria = db.query(PrestamoDB, InventarioDB.estanteria)\
        .outerjoin(InventarioDB, (PrestamoDB.nombre_item == InventarioDB.titulo) & (PrestamoDB.tipo_item == 'Libro'))\
        .filter(PrestamoDB.estado == 'Activo')\
        .order_by(PrestamoDB.fecha_devolucion.asc())\
        .all()
    
    resultado = []
    for p, estanteria in prestamos_con_estanteria:
        resultado.append({
            "id": p.id,
            "tipo_item": p.tipo_item,
            "nombre_item": p.nombre_item,
            "nombre_alumno": p.nombre_alumno,
            "curso": p.curso,
            "fecha_prestamo": p.fecha_prestamo,
            "fecha_devolucion": p.fecha_devolucion,
            "estado": p.estado,
            "estanteria": estanteria
        })
        
    return resultado

@app.get("/api/prestamos/alerta-pendiente")
def check_alertas_pendientes(current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    hoy = datetime.now().strftime("%Y-%m-%d")
    pendientes = db.query(PrestamoDB).filter(PrestamoDB.estado == 'Activo', PrestamoDB.fecha_devolucion < hoy).all()
    
    detalles = [
        {"nombre_item": p.nombre_item, "nombre_alumno": p.nombre_alumno, "fecha_devolucion": p.fecha_devolucion} 
        for p in pendientes
    ]
    
    return {"tiene_pendientes": len(detalles) > 0, "detalles": detalles}

@app.put("/api/prestamos/{prestamo_id}/devolver")
def devolver_prestamo(prestamo_id: int, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    prestamo = db.query(PrestamoDB).filter(PrestamoDB.id == prestamo_id).first()
    
    if not prestamo:
        raise HTTPException(status_code=404, detail="Préstamo no encontrado")
        
    prestamo.estado = 'Devuelto'
    db.commit()
    
    return {"mensaje": "Préstamo marcado como devuelto"}

# --- Historial de Alumno ---
@app.get("/api/alumnos/{nombre_alumno}/historial")
def get_historial_alumno(nombre_alumno: str, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    # Traer todos los préstamos del alumno
    prestamos = db.query(PrestamoDB, InventarioDB.tematicas)\
        .outerjoin(InventarioDB, (PrestamoDB.nombre_item == InventarioDB.titulo) & (PrestamoDB.tipo_item == 'Libro'))\
        .filter(PrestamoDB.nombre_alumno == nombre_alumno)\
        .order_by(PrestamoDB.fecha_prestamo.desc())\
        .all()
    
    lista_prestamos = []
    todas_tematicas = []
    
    for p, tematicas in prestamos:
        lista_prestamos.append({
            "id": p.id,
            "tipo_item": p.tipo_item,
            "nombre_item": p.nombre_item,
            "fecha_prestamo": p.fecha_prestamo,
            "fecha_devolucion": p.fecha_devolucion,
            "estado": p.estado
        })
        if tematicas:
            # Dividir temáticas separadas por coma
            temas = [t.strip() for t in tematicas.split(",") if t.strip()]
            todas_tematicas.extend(temas)
            
    # Contar temáticas
    contador_tematicas = dict(Counter(todas_tematicas))
    
    return {
        "alumno": nombre_alumno,
        "prestamos": lista_prestamos,
        "tematicas": contador_tematicas
    }

# --- Endpoint Estadísticas ---
@app.get("/api/estadisticas")
def get_estadisticas(current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    # 1. Total de Libros
    total_libros = db.query(InventarioDB).count()
    
    # 2. Total de Materiales
    total_materiales = db.query(MaterialDB).count()
    
    # 3. Total de Préstamos Activos
    prestamos_activos = db.query(PrestamoDB).filter(PrestamoDB.estado == 'Activo').count()
    
    # 4. Obtener temáticas y niveles
    inventario_stats = db.query(InventarioDB.nivel, InventarioDB.tematicas).all()
    
    niveles = []
    tematicas_list = []
    
    for nivel, tematicas in inventario_stats:
        if nivel: niveles.append(nivel)
        if tematicas:
            temas = [t.strip() for t in tematicas.split(",") if t.strip()]
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
def generar_recomendacion_ia(req: RecomendacionRequest, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="API Key de Gemini no configurada en las variables de entorno.")
        
    # Obtener el catálogo actual para dárselo de contexto a la IA
    libros = db.query(InventarioDB.titulo, InventarioDB.autor).all()
    
    catalogo_texto = ", ".join([f"'{l.titulo}' por {l.autor}" for l in libros])
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
        modelo = genai.GenerativeModel("gemini-2.5-flash")
        respuesta = modelo.generate_content(prompt_rec)
        return {"respuesta": respuesta.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar recomendación: {str(e)}")

@app.post("/api/generar-evento-ia")
def generar_evento_ia(req: GenerarEventoRequest, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="API Key de Gemini no configurada.")
        
    libros = db.query(InventarioDB.titulo, InventarioDB.autor, InventarioDB.nivel).all()
    
    catalogo_texto = ", ".join([f"'{l.titulo}' por {l.autor} ({l.nivel})" for l in libros])
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
        raise HTTPException(status_code=500, detail=f"Error al planificar evento: {str(e)}")

# --- Recomendación Diaria IA ---
@app.get("/api/recomendacion-diaria")
def get_recomendacion_diaria(db: Session = Depends(get_db)):
    if not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="API Key de Gemini no configurada en las variables de entorno.")
        
    # Obtener todos los libros
    libros = db.query(InventarioDB.titulo, InventarioDB.autor).all()
    if not libros:
        return {"titulo": "N/A", "autor": "N/A", "mensaje": "El catálogo está vacío."}
        
    # Contar préstamos por libro
    prestamos = db.query(PrestamoDB.nombre_item).filter(PrestamoDB.tipo_item == 'Libro').all()
    contador_prestamos = Counter([p.nombre_item for p in prestamos])
    
    # Ordenar libros por cantidad de préstamos (ascendente)
    libros_con_conteo = [(l.titulo, l.autor, contador_prestamos.get(l.titulo, 0)) for l in libros]
    libros_con_conteo.sort(key=lambda x: x[2])
    
    # Tomar los 10 menos prestados
    menos_prestados = libros_con_conteo[:10]
    
    lista_libros_str = ", ".join([f"'{l[0]}' de {l[1]}" for l in menos_prestados])
    
    # Fecha formateada
    meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    hoy = datetime.now()
    hoy_str = f"{hoy.day} de {meses[hoy.month - 1]} de {hoy.year}"
    
    prompt = f"""
    Hoy es {hoy_str}. Sugiere un libro del catálogo adjunto para recomendar en el CRA.
    El objetivo es fomentar la lectura de títulos poco conocidos y conectarlos con la efeméride actual si existe, o dar una motivación atractiva para los niños y adolescentes.
    
    Catálogo de libros menos leídos: {lista_libros_str}
    
    Devuelve estrictamente un objeto JSON válido con la siguiente estructura (sin bloques de código markdown ni comillas triples):
    {{
      "titulo": "Título del libro",
      "autor": "Autor del libro",
      "mensaje": "Mensaje motivacional (2-3 oraciones breves)..."
    }}
    """
    
    try:
        modelo = genai.GenerativeModel("gemini-2.5-flash")
        respuesta = modelo.generate_content(prompt)
        texto = respuesta.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(texto)
        return data
    except Exception as e:
        print("Error de IA:", str(e))
        # Fallback de emergencia
        return {
            "titulo": menos_prestados[0][0], 
            "autor": menos_prestados[0][1], 
            "mensaje": "¡Te invitamos a descubrir esta joya oculta de nuestra biblioteca hoy mismo!"
        }

@app.post("/api/migrar-csv")
def migrar_csv(current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    # Rutas a los archivos originales (ajusta si los moviste de carpeta)
    ruta_inventario = r"..\cami CRA\inventario_libros.csv"
    ruta_eventos = r"..\cami CRA\eventos_cra.csv"
    
    resultados = {"inventario_insertados": 0, "eventos_insertados": 0, "errores": []}
    
    # Migrar Inventario
    try:
        if os.path.exists(ruta_inventario):
            with open(ruta_inventario, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    nuevo_libro = InventarioDB(
                        titulo=row.get("Título", ""),
                        autor=row.get("Autor", ""),
                        nivel=row.get("Nivel Recomendado", ""),
                        tematicas=row.get("Temáticas", "")
                    )
                    db.add(nuevo_libro)
                    resultados["inventario_insertados"] += 1
            db.commit()
        else:
            resultados["errores"].append("inventario_libros.csv no encontrado.")
    except Exception as e:
        db.rollback()
        resultados["errores"].append(f"Error migrando inventario: {str(e)}")

    # Migrar Eventos
    try:
        if os.path.exists(ruta_eventos):
            with open(ruta_eventos, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    nuevo_evento = EventoDB(
                        nombre_evento=row.get("Nombre Evento", ""),
                        fecha=row.get("Fecha", ""),
                        objetivo=row.get("Objetivo", ""),
                        libros_seleccionados=row.get("Libros Seleccionados", ""),
                        materiales="",
                        resultados=""
                    )
                    db.add(nuevo_evento)
                    resultados["eventos_insertados"] += 1
            db.commit()
        else:
            resultados["errores"].append("eventos_cra.csv no encontrado.")
    except Exception as e:
        db.rollback()
        resultados["errores"].append(f"Error migrando eventos: {str(e)}")

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
