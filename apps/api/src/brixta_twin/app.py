from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .blending import preview_blend
from .models import Blend,BlendCreate,BlendPreview,Machine,MachineCreate,Material,MaterialCreate,Route,RouteCreate,RunRequest,RunResult,new_id,now
from .seed import seed
from .simulation import Engine
from .storage import Repository


def create_app(path: str|Path|None=None)->FastAPI:
    repo=Repository(path); seed(repo); engine=Engine(repo)
    app=FastAPI(title="BRIXTA Cement Twin API",version="0.2.0")
    app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],allow_methods=["*"],allow_headers=["*"])
    @app.get("/api/health")
    def health(): return {"status":"ok","service":"brixta-cement-twin-api"}
    @app.get("/api/materials",response_model=list[Material])
    def materials(): return repo.list("materials")
    @app.post("/api/materials",response_model=Material)
    def add_material(p:MaterialCreate): return repo.save("materials",Material(**p.model_dump(),material_id=new_id("mat"),created_at=now()))
    @app.get("/api/blends",response_model=list[Blend])
    def blends(): return repo.list("blends")
    @app.post("/api/blends/preview",response_model=BlendPreview)
    def preview_new_blend(p:BlendCreate):
        try: return preview_blend(repo,p)
        except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    @app.get("/api/blends/{blend_id}/preview",response_model=BlendPreview)
    def preview_saved_blend(blend_id:str):
        blend=repo.get("blends",blend_id)
        if not isinstance(blend,Blend): raise HTTPException(404,"Unknown blend")
        try: return preview_blend(repo,blend,root_id=blend.blend_id)
        except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    @app.post("/api/blends",response_model=Blend)
    def add_blend(p:BlendCreate):
        blend=Blend(**p.model_dump(),blend_id=new_id("blend"),created_at=now())
        try: preview_blend(repo,blend,root_id=blend.blend_id)
        except ValueError as exc: raise HTTPException(422,str(exc)) from exc
        return repo.save("blends",blend)
    @app.get("/api/machines",response_model=list[Machine])
    def machines(): return repo.list("machines")
    @app.post("/api/machines",response_model=Machine)
    def add_machine(p:MachineCreate): return repo.save("machines",Machine(**p.model_dump(),machine_id=new_id("machine"),created_at=now()))
    @app.get("/api/routes",response_model=list[Route])
    def routes(): return repo.list("routes")
    @app.post("/api/routes",response_model=Route)
    def add_route(p:RouteCreate): return repo.save("routes",Route(**p.model_dump(),route_id=new_id("route"),created_at=now()))
    @app.post("/api/runs",response_model=RunResult)
    def run(p:RunRequest):
        try: return engine.run(p)
        except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    @app.get("/api/runs",response_model=list[RunResult])
    def runs(): return repo.list("runs")
    return app


app=create_app()
