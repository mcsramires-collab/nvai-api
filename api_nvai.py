from fastapi import FastAPI, Header, HTTPException
from supabase import create_client, Client
import uvicorn
import unicodedata
import os

app = FastAPI()

# ====================================================
# CONFIGURAÇÃO SUPABASE - LIMPEZA AUTOMÁTICA
# ====================================================
# COLOQUE AQUI A URL QUE TERMINA EM .co
RAW_URL = "https://gbtvusyjolpautvyddvh.supabase.co" 
# Remove barras extras ou espaços que podem causar o erro 404
SUPABASE_URL = RAW_URL.strip().rstrip('/')

SUPABASE_KEY = "sb_publishable_b1nsi_xHaSjm1BQbBToXIA_-6TaOtb5"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"❌ ERRO DE CONFIGURAÇÃO: {e}")

def limpar_texto(texto):
    if not texto: return "Ocioso"
    nfkd = unicodedata.normalize('NFKD', str(texto))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).encode('ascii', 'ignore').decode('ascii')

@app.post("/enviar_log")
async def receber_log(payload: dict, x_api_key: str = Header(None)):
    try:
        # Validação simples de segurança
        if not x_api_key:
            raise HTTPException(status_code=401, detail="Chave ausente")

        # Verifica se a empresa existe
        empresa = supabase.table("empresas").select("id").eq("api_key", x_api_key).execute()
        
        if not empresa.data:
            raise HTTPException(status_code=401, detail="Empresa nao cadastrada")

        # Prepara o registro para o banco
        registro = {
            "empresa_id": empresa.data[0]["id"],
            "funcionario": limpar_texto(payload.get("funcionario")),
            "equipe": limpar_texto(payload.get("equipe")),
            "janela": limpar_texto(payload.get("janela")),
            "cpu": float(payload.get("cpu", 0)),
            "ram": float(payload.get("ram", 0)),
            "ping": float(payload.get("ping", 0))
        }

        # Insere na tabela 'logs'
        supabase.table("logs").insert(registro).execute()
        return {"status": "sucesso"}

    except Exception as e:
        # Retorna o erro exato para o Agente ler no terminal
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
