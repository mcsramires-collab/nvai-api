from fastapi import FastAPI, Header, HTTPException
from supabase import create_client, Client
import os

app = FastAPI()

# Substitua pelas suas credenciais do Supabase (Project Settings > API)
SUPABASE_URL = "https://supabase.com/dashboard/project/gbtvusyjolpautvyddvh"
SUPABASE_KEY = "sb_publishable_b1nsi_xHaSjm1BQbBToXIA_-6TaOtb5"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.post("/enviar_log")
async def receber_log(dados: dict, x_api_key: str = Header(None)):
    # 1. Valida se a API Key da empresa é real
    empresa = supabase.table("empresas").select("id").eq("api_key", x_api_key).execute()
    
    if not empresa.data:
        raise HTTPException(status_code=401, detail="API Key Invalida")

    # 2. Insere o dado no banco com o ID da empresa correta
    dados["empresa_id"] = empresa.data[0]["id"]
    resposta = supabase.table("logs").insert(dados).execute()
    
    return {"status": "sucesso", "data": resposta.data}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)