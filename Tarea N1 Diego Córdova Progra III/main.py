from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
from models import Personaje, Mision, MisionPersonaje
from cola import Cola

Base.metadata.create_all(bind=engine)

app = FastAPI()
colas_por_personaje = {}  # Diccionario con colas por ID de personaje

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/personajes")
def crear_personaje(nombre: str, db: Session = Depends(get_db)):
    nuevo = Personaje(nombre=nombre)
    db.add(nuevo)
    db.commit()
    colas_por_personaje[nuevo.id] = Cola()
    return {"mensaje": "Personaje creado", "id": nuevo.id}

@app.post("/misiones")
def crear_mision(nombre: str, descripcion: str = "", experiencia: int = 10, db: Session = Depends(get_db)):
    mision = Mision(nombre=nombre, descripcion=descripcion, experiencia=experiencia, estado='pendiente')
    db.add(mision)
    db.commit()
    return {"mensaje": "Misión creada", "id": mision.id}

@app.post("/personajes/{personaje_id}/misiones/{mision_id}")
def aceptar_mision(personaje_id: int, mision_id: int, db: Session = Depends(get_db)):
    cola = colas_por_personaje.setdefault(personaje_id, Cola())
    orden = cola.size()
    cola.enqueue(mision_id)

    rel = MisionPersonaje(personaje_id=personaje_id, mision_id=mision_id, orden=orden)
    db.add(rel)
    db.commit()
    return {"mensaje": "Misión encolada"}

@app.post("/personajes/{personaje_id}/completar")
def completar_mision(personaje_id: int, db: Session = Depends(get_db)):
    cola = colas_por_personaje.get(personaje_id)
    if not cola or cola.is_empty():
        return {"error": "No hay misiones pendientes"}

    mision_id = cola.dequeue()
    mision = db.get(Mision, mision_id)
    personaje = db.get(Personaje, personaje_id)
    if mision:
        mision.estado = 'completada'
        personaje.experiencia += mision.experiencia
        db.commit()
        return {"mensaje": f"Misión '{mision.nombre}' completada", "xp_total": personaje.experiencia}
    return {"error": "Misión no encontrada"}

@app.get("/personajes/{personaje_id}/misiones")
def listar_misiones(personaje_id: int, db: Session = Depends(get_db)):
    cola = colas_por_personaje.get(personaje_id)
    if not cola:
        return {"misiones": []}
    ids = cola.items
    misiones = db.query(Mision).filter(Mision.id.in_(ids)).all()
    return [{"id": m.id, "nombre": m.nombre, "estado": m.estado} for m in misiones]
