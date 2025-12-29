from fastapi import FastAPI, Header, HTTPException
from supabase import create_client, Client
import uvicorn
import base64
import unicodedata
import os

app = FastAPI(title="NVAI Global SaaS API")

# ====================================================
# CONFIGURAÇÃO SUPABASE
# ====================================================
SUPABASE_URL = "https://gbtvusyjolpautvyddvh.supabase.co"
SUPABASE_KEY = "sb_publishable_b1nsi_xHaSjm1BQbBToXIA_-6TaOtb5"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ====================================================
# UTILITÁRIOS
# ====================================================
def decodificar_chave(chave):
    """Decodifica a chave Base64 para validação interna."""
    try:
        decoded = base64.b64decode(chave).decode('utf-8')
        return decoded.split('|') # NVAI|CNPJ|NIVEL|EQUIPE
    except:
        return None

def limpar_texto(texto):
    if not texto: return "Ocioso"
    nfkd = unicodedata.normalize('NFKD', str(texto))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).encode('ascii', 'ignore').decode('ascii')

# ====================================================
# ROTAS DE GESTÃO E LOGS
# ====================================================

@app.get("/")
async def root():
    return {"status": "NVAI SaaS Gateway Online", "versao": "4.1.0"}

@app.post("/ativar")
async def ativar_licenca(dados: dict):
    """
    Rota de Ativação (Ponto 4 do seu fluxo):
    Recebe a chave informada pelo usuário e vincula ao hardware do PC.
    """
    chave = dados.get("chave")
    hw_id = dados.get("hw_id")

    if not chave or not hw_id:
        raise HTTPException(status_code=400, detail="Chave e HW_ID obrigatorios")

    # 1. Verifica se a chave existe na tabela de licenças
    query = supabase.table("licencas").select("*").eq("chave_ativacao", chave).execute()
    
    if not query.data:
        raise HTTPException(status_code=401, detail="Chave de ativacao invalida")
    
    lic = query.data[0]
    
    # 2. Verifica se já está vinculada a outra máquina (Antipirataria)
    if lic['status'] == 'vinculado' and lic['hardware_id'] != hw_id:
        raise HTTPException(status_code=403, detail="Chave ja vinculada a outro computador")

    if lic['status'] == 'suspenso':
        raise HTTPException(status_code=403, detail="Esta licenca esta suspensa")

    # 3. Realiza o vínculo
    try:
        supabase.table("licencas").update({
            "hardware_id": hw_id, 
            "status": "vinculado"
        }).eq("chave_ativacao", chave).execute()
        
        return {"status": "sucesso", "mensagem": "Sistema ativado com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@app.post("/enviar_log")
async def receber_log(payload: dict, x_api_key: str = Header(None)):
    """
    Recebe os logs a cada 5 minutos.
    Valida se a assinatura continua ativa.
    """
    hw_id_cliente = payload.get("hw_id")
    
    # 1. Valida a licença e o hardware no banco
    validacao = supabase.table("licencas").select("status, hardware_id, empresa_id, nivel, equipe").eq("chave_ativacao", x_api_key).execute()
    
    if not validacao.data:
        raise HTTPException(status_code=401, detail="Licenca nao reconhecida")
    
    lic = validacao.data[0]
    
    # COMANDO REMOTO DE DESATIVAÇÃO (Ponto 3 do seu fluxo)
    # Se você mudar o status para 'suspenso' no banco, o robô morre no próximo envio
    if lic['status'] != 'vinculado' or lic['hardware_id'] != hw_id_cliente:
        return {"status": "erro", "comando": "DESATIVAR", "motivo": "Bloqueio administrativo ou hardware divergente"}

    # 2. Cálculo de Custo de Ociosidade
    id_emp = lic['empresa_id']
    func_id = payload.get("funcionario")
    config = supabase.table("configuracoes_usuarios").select("salario_mensal, horas_mensais").eq("empresa_id", id_emp).eq("funcionario_id", func_id).execute()
    
    custo_min = 0
    if config.data:
        salario = config.data[0].get('salario_mensal', 0)
        horas = config.data[0].get('horas_mensais', 220)
        custo_min = (salario / (horas if horas > 0 else 220)) / 60

    # 3. Gravação do Log
    registro = {
        "empresa_id": id_emp,
        "funcionario": limpar_texto(func_id),
        "equipe": lic['equipe'],
        "janela": limpar_texto(payload.get("janela")),
        "cpu": float(payload.get("cpu", 0)),
        "ram": float(payload.get("ram", 0)),
        "custo_minuto": custo_min,
        "nivel_origem": lic['nivel']
    }

    try:
        supabase.table("logs").insert(registro).execute()
        return {"status": "sucesso", "intervalo_s": 300, "comando": "CONTINUAR"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
