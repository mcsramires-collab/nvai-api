from fastapi import FastAPI, Header, HTTPException
from supabase import create_client, Client
import uvicorn
import unicodedata
import os

app = FastAPI()

# ====================================================
# CONFIGURAÇÃO SUPABASE
# ====================================================
SUPABASE_URL = "https://supabase.com/dashboard/project/gbtvusyjolpautvyddvh"
SUPABASE_KEY = "sb_publishable_b1nsi_xHaSjm1BQbBToXIA_-6TaOtb5"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def limpar_texto(texto):
    if not texto: return "Ocioso"
    nfkd = unicodedata.normalize('NFKD', str(texto))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).encode('ascii', 'ignore').decode('ascii')

@app.get("/")
async def root():
    return {"status": "NVAI Online", "versao": "3.0.1"}

@app.post("/enviar_log")
async def receber_log(payload: dict, x_api_key: str = Header(None)):
    try:
        if not x_api_key:
            raise HTTPException(status_code=401, detail="API Key ausente")

        # 1. Validar empresa
        empresa = supabase.table("empresas").select("id").eq("api_key", x_api_key).execute()
        
        if not empresa.data:
            raise HTTPException(status_code=401, detail="API Key Invalida")

        empresa_id = empresa.data[0]["id"]

        # 2. Preparar registro (Nomes das colunas devem ser IDÊNTICOS ao Supabase)
        registro = {
            "empresa_id": empresa_id,
            "funcionario": limpar_texto(payload.get("funcionario")),
            "equipe": limpar_texto(payload.get("equipe")),
            "janela": limpar_texto(payload.get("janela")),
            "cpu": float(payload.get("cpu", 0)),
            "ram": float(payload.get("ram", 0)),
            "ping": float(payload.get("ping", 0))
        }

        # 3. Inserir no banco
        resultado = supabase.table("logs").insert(registro).execute()
        return {"status": "sucesso"}

    except Exception as e:
        # Isso vai imprimir o erro real nos logs do Render para você ler
        print(f"DEBUG ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

