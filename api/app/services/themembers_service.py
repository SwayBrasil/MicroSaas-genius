# app/services/themembers_service.py
"""
Serviço de integração com The Members API.
"""
import os
from typing import Optional, Dict, Any, List
import httpx
from fastapi import HTTPException

THEMEMBERS_DEV_TOKEN = os.getenv("THEMEMBERS_DEV_TOKEN", "93c911d3-4580-4de7-a02b-db67fd9af8fe")
THEMEMBERS_PLATFORM_TOKEN = os.getenv("THEMEMBERS_PLATFORM_TOKEN", "1644d350-82d5-4004-a52a-56bff805126e")
THEMEMBERS_BASE_URL = os.getenv("THEMEMBERS_BASE_URL", "https://registration.themembers.dev.br/api")


async def get_products() -> List[Dict[str, Any]]:
    """
    Busca todos os produtos da The Members.
    
    Returns:
        Lista de produtos com seus dados completos.
    """
    url = f"{THEMEMBERS_BASE_URL}/products/all-products/{THEMEMBERS_DEV_TOKEN}/{THEMEMBERS_PLATFORM_TOKEN}"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            
            # A API pode retornar em diferentes formatos
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "products" in data:
                return data["products"]
            elif isinstance(data, dict):
                return [data]
            else:
                return []
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=500,
                detail=f"TheMembers API error: {e.response.status_code} - {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching products: {str(e)}"
            )


async def get_user_by_email(email: str) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Busca usuário na The Members pelo email.
    
    Args:
        email: Email do usuário
        
    Returns:
        Tupla (user, subscription) ou (None, None) se não encontrado.
    """
    url = f"{THEMEMBERS_BASE_URL}/users/show-email/{email}/{THEMEMBERS_DEV_TOKEN}/{THEMEMBERS_PLATFORM_TOKEN}"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url)
            
            if resp.status_code == 200:
                data = resp.json()
                return data.get("user"), data.get("subscription")
            
            if resp.status_code == 404:
                return None, None
            
            # Qualquer outra coisa tratamos como erro
            raise HTTPException(
                status_code=500,
                detail=f"TheMembers error: {resp.status_code} - {resp.text}"
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching user: {str(e)}"
            )


async def create_user_with_product(
    email: str,
    name: str,
    last_name: str,
    document: str | None = None,
    phone: str | None = None,
    reference_id: str | None = None,
    accession_date: str | None = None,
    product_id: str | None = None,
) -> Dict[str, Any]:
    """
    Cria usuário + assinatura em um passo, usando o endpoint /users/create.
    
    Args:
        email: Email do usuário
        name: Primeiro nome
        last_name: Sobrenome
        document: CPF/CNPJ (opcional)
        phone: Telefone (opcional)
        reference_id: ID de referência externa (ex: order_id da Eduzz)
        accession_date: Data de adesão (formato YYYY-MM-DD)
        product_id: ID do produto na The Members
        
    Returns:
        Resposta completa da API The Members
    """
    if not product_id:
        product_id = os.getenv("THEMEMBERS_DEFAULT_PRODUCT_ID", "2352153")
    
    url = f"{THEMEMBERS_BASE_URL}/users/create/{THEMEMBERS_DEV_TOKEN}/{THEMEMBERS_PLATFORM_TOKEN}"

    payload = {
        "product_id": [product_id],
        "users": [
            {
                "name": name,
                "last_name": last_name,
                "email": email,
                "document": document,
                "phone": phone,
                "reference_id": reference_id,
                "accession_date": accession_date or "2025-01-01",
            }
        ],
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=500,
                detail=f"TheMembers create user error: {e.response.status_code} - {e.response.text}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error creating user: {str(e)}"
            )


async def get_course_reports(
    product_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> Dict[str, Any]:
    """
    Busca relatórios de cursos/produtos da The Members.
    
    Args:
        product_id: ID do produto (opcional)
        start_date: Data inicial (formato YYYY-MM-DD)
        end_date: Data final (formato YYYY-MM-DD)
        
    Returns:
        Dados de relatórios
    """
    # Monta URL com parâmetros opcionais
    base_url = f"{THEMEMBERS_BASE_URL}/reports/course-reports/{THEMEMBERS_DEV_TOKEN}/{THEMEMBERS_PLATFORM_TOKEN}"
    
    params = {}
    if product_id:
        params["product_id"] = product_id
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(base_url, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=500,
                detail=f"TheMembers reports error: {e.response.status_code} - {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching reports: {str(e)}"
            )


